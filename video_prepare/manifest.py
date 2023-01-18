from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import timedelta
import os
from multiprocessing import cpu_count
import shutil
import tempfile

import pandas as pd
import pytz
import video_io

from . import util
from .log import logger


class Manifest:
    def __init__(
        self,
        video_metadata=None,
        start=None,
        end=None,
        output_directory="",
        empty_clip_path="",
        raw_video_storage_directory=None,
    ):
        if video_metadata is None:
            video_metadata = []

        self.captured_video_list = []
        self.missing_video_list = []
        self.downloaded_video_list = []

        self.video_metadata = video_metadata

        if isinstance(end, str):
            self.end_datetime = util.str_to_date(end)
        else:
            self.end_datetime = end

        if isinstance(start, str):
            self.start_datetime = util.str_to_date(start)
        else:
            self.start_datetime = start

        self.output_directory = output_directory
        util.create_dir(self.output_directory)

        self.empty_clip_path = empty_clip_path
        self.raw_video_storage_directory = raw_video_storage_directory

        self.process_video_metadata()

    def process_video_metadata(self):
        """
        Parse the video_metadata list. Track any missing videos not known to the video API service and track all video
        files that should be downloaded (or copied from the local EFS volume if available)
        """

        datetimeindex = pd.date_range(
            self.start_datetime, self.end_datetime - timedelta(seconds=10), freq="10S", tz=pytz.UTC
        )

        # Convert datapoints to a dataframe to use pd timeseries functionality
        df_datapoints = pd.DataFrame(self.video_metadata)
        if len(self.video_metadata) > 0:
            # Move timestamp column to datetime index
            df_datapoints["video_timestamp"] = pd.to_datetime(df_datapoints["video_timestamp"], utc=True)
            df_datapoints = df_datapoints.set_index(pd.DatetimeIndex(df_datapoints["video_timestamp"]))
            df_datapoints = df_datapoints.drop(columns=["video_timestamp"])
            # Scrub duplicates (these shouldn't exist)
            df_datapoints = df_datapoints[~df_datapoints.index.duplicated(keep="first")]

        # Fill in missing time indices
        df_datapoints = df_datapoints.reindex(datetimeindex)
        # TODO: Consider handling empty df_datapoints and lining it up with timestamps that cover a given start and end time
        for idx_datetime, row in df_datapoints.iterrows():
            start_formatted_time = util.clean_pd_ts(idx_datetime)
            end_formatted_time = util.clean_pd_ts(idx_datetime + timedelta(seconds=10))
            # output = os.path.join(target, f"{start_formatted_time}.video.mp4")

            if "data_id" not in row or pd.isnull(row["data_id"]) or "path" not in row or pd.isnull(row["path"]):
                self.add_to_missing(start=start_formatted_time, end=end_formatted_time)
            else:
                self.add_to_download(video_metadatum=row.to_dict(), start=start_formatted_time, end=end_formatted_time)

    def get_files(self):
        # last_available_video_end_time = self.get_last_valid_clip_end_time()

        files = copy.copy(self.captured_video_list)

        for missing_file in self.missing_video_list:
            files.append(missing_file)
            # if last_available_video_end_time is not None and missing_file["start"] < last_available_video_end_time:
            #     files.append(missing_file)

        return files

    def add_to_download(self, video_metadatum, start, end):
        video_metadatum["start"] = util.str_to_date(start)
        video_metadatum["end"] = util.str_to_date(end)

        file_extension = os.path.splitext(video_metadatum["path"])[1]
        video_timestamp = video_metadatum["start"].strftime("%Y-%m-%dT%H:%M:%SZ")
        new_path = os.path.join(
            self.output_directory, f"{video_timestamp}_{video_metadatum['data_id']}{file_extension}"
        )
        video_metadatum["video_streamer_path"] = new_path

        self.captured_video_list.append(video_metadatum)

    def add_to_missing(self, start, end):
        self.missing_video_list.append(
            {
                "video_streamer_path": self.empty_clip_path,
                "start": util.str_to_date(start),
                "end": util.str_to_date(end),
            }
        )

    def get_last_valid_clip_end_time(self):
        last_available_video_end_time = None
        if len(self.captured_video_list) > 0:
            last_available_video_end_time = self.captured_video_list[-1]["end"]

        return last_available_video_end_time

    def download_or_copy_files(self, workers=cpu_count() - 1):
        missing_video = []
        video_needing_download = []

        # 1. First filter out any videos already available on disk
        for v in self.captured_video_list:
            if not os.path.exists(v["video_streamer_path"]):
                missing_video.append(v)

        def copy_from_raw_video_storage(video):
            copy_success = False
            if self.raw_video_storage_directory:
                raw_video_path = os.path.join(self.raw_video_storage_directory, video["path"])
                print(raw_video_path)
                if os.path.exists(raw_video_path):
                    try:
                        shutil.copy(raw_video_path, video["video_streamer_path"])
                        logger.info(
                            f"Copied '{raw_video_path}' to final storage path '{video['video_streamer_path']}' successfully"
                        )
                        copy_success = True
                    except Exception as ex:
                        warning = f"Failed copying raw video '{raw_video_path}' to final storage path '{video['video_streamer_path']}', will attempt to download file using video_io service"
                        logger.warning(warning)

            return video, copy_success

        # 2. Try to copy videos from the raw_video_directory (if that's available)
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = executor.map(copy_from_raw_video_storage, missing_video)
            executor.shutdown(wait=True)

        for (v, success) in results:
            if not success:
                video_needing_download.append(v)

        # 3. After attempting to copy the video file, fall back to downloading the file
        #    Files are first downloaded to a tmp directory before they are moved to permanent storage (files are renamed when they are moved)
        with tempfile.TemporaryDirectory() as tmp_dir:
            videos = video_io.download_video_files(
                video_metadata=video_needing_download, local_video_directory=tmp_dir, max_workers=workers
            )

            for downloaded_file in video_needing_download:
                try:
                    shutil.move(downloaded_file["video_local_path"], downloaded_file["video_streamer_path"])
                except Exception as ex:
                    err = f"Failed copying downloaded video '{downloaded_file['video_local_path']}' to final storage path '{downloaded_file['video_streamer_path']}'"
                    logger.error(err)
                    raise ex

        # Return a list of all files that were downloaded
        return videos

    def execute(self):
        return self.download_or_copy_files()
