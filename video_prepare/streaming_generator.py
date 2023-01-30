from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import timedelta
import os
from multiprocessing import cpu_count
import shutil
import tempfile
from typing import Optional

import pandas as pd
import pytz
import video_io

from . import util
from .log import logger
from .transcode import (
    concat_videos,
    count_frames,
    generate_preview_image,
    pad_video,
    prepare_hls,
    trim_video,
)


class StreamingGenerator:
    """
    The StreamingGenerator is responsible for parsing video_metadata, fetching videos from the video_io service, preparing those videos (trimming/padding), and converting the videos into streamable video.
    """

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

        self.loaded = False

        self._reset_lists()
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

        self.hls_path = os.path.join(output_directory, "output.m3u8")
        self.preview_image_path = os.path.join(output_directory, "output-preview.jpg")
        self.m3u8_files_path = os.path.join(output_directory, "m3u8_files.txt")
        self.video_out_path = os.path.join(output_directory, "output.mp4")

        self.empty_clip_path = empty_clip_path

        # On production, this is the EFS mount where raw videos are stored and copied from
        self.raw_video_storage_directory = raw_video_storage_directory

    def _reset_lists(self):
        self.captured_video_list = []
        self.missing_video_list = []
        self.downloaded_video_list = []

    def load(self):
        if not self.loaded:
            self._process_video_metadata()

        self.loaded = True
        return self

    def cleanup(self, remove_processed_files=False):
        if remove_processed_files:
            logger.info(
                f"Deleting all previously downloaded/copied raw video files and all staged mp4s used to generating streaming video"
            )
            for item in os.listdir(self.output_directory):
                if item.endswith(".mp4"):
                    os.remove(os.path.join(self.output_directory, item))

        self._reset_lists()
        self.loaded = False

    def _process_video_metadata(self):
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

    def get_files(self) -> Optional[pd.DataFrame]:
        if not self.loaded:
            logger.warning(
                "Calling StreamingGenerator::get_files before load() method has been called. May misleadingly make it appear there are no videos to process."
            )

        files = copy.copy(self.captured_video_list)

        for missing_file in self.missing_video_list:
            files.append(missing_file)

        if len(files) == 0:
            return None

        df_files = pd.DataFrame(files)
        df_files.index = pd.to_datetime(df_files["start"])
        df_files = df_files.sort_index()
        return df_files

    def file_count(self):
        if not self.loaded:
            logger.warning(
                "Calling StreamingGenerator::file_count before load() method has been called. May misleadingly make it appear there are no videos to process."
            )

        files = self.get_files()
        if files is None or len(files) == 0:
            return 0

        return len(files)

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
        logger.info("Downloading/copying raw video files")

        video_not_on_disk = []
        video_needing_download = []

        # 1. First filter out any videos already available on disk
        for v in self.captured_video_list:
            if not os.path.exists(v["video_streamer_path"]):
                video_not_on_disk.append(v)

        def _copy_from_raw_video_storage(video):
            copy_success = False
            if self.raw_video_storage_directory:
                raw_video_path = os.path.join(self.raw_video_storage_directory, video["path"])

                if os.path.exists(raw_video_path):
                    try:
                        shutil.copy(raw_video_path, video["video_streamer_path"])
                        logger.info(
                            f"Copied '{raw_video_path}' to final storage path '{video['video_streamer_path']}' successfully"
                        )
                        copy_success = True
                    except Exception:
                        warning = f"Failed copying raw video '{raw_video_path}' to final storage path '{video['video_streamer_path']}', will attempt to download file using video_io service"
                        logger.warning(warning)

            return video, copy_success

        # 2. Try to copy videos from the raw_video_directory (if that's available)
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = executor.map(_copy_from_raw_video_storage, video_not_on_disk)
            executor.shutdown(wait=True)

        for (v, success) in results:
            if not success:
                video_needing_download.append(v)

        # 3. After attempting to copy the video files, fall back to downloading the files
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

    def process_raw_files(self):
        logger.info("Processing raw video files, verifying FPS and file length")

        def _process(file_tuple):
            idx, file = file_tuple
            video_snippet_path = file["video_streamer_path"]

            # Process new video files
            logger.info(f"Preparing '{video_snippet_path}' for HLS generation...")
            try:
                num_frames = count_frames(video_snippet_path)
            except Exception:
                logger.warning(f"Unable to probe '{video_snippet_path}', replacing with empty video clip")
                video_snippet_path = self.empty_clip_path
                num_frames = count_frames(video_snippet_path)

            if num_frames < 100:
                pad_video(video_snippet_path, video_snippet_path, frames=(100 - num_frames))
            if num_frames > 100:
                trim_video(video_snippet_path, video_snippet_path, duration=10)

            num_frames = 100

            return num_frames, file

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = executor.map(_process, self.get_files().iterrows())
            executor.shutdown(wait=True)

        with open(self.m3u8_files_path, "w", encoding="utf-8") as fp:
            count = 0
            for num_frames, file in results:
                video_snippet_path = file["video_streamer_path"]

                fp.write(
                    f"file 'file:{video_snippet_path}' duration 00:00:{util.format_frames(num_frames)} inpoint {util.vts(count)} outpoint {util.vts(count + num_frames)}\n"
                )

                count += num_frames
            fp.flush()

    def generate_hls_feed(self, rewrite):
        logger.info(f"Generating video for subsequent conversion to HLS: {self.video_out_path}...")
        concat_videos(input_path=self.m3u8_files_path, output_path=self.video_out_path, rewrite=True)
        logger.info(f"Generated video: {self.video_out_path}")

        logger.info(f"Generating HLS stream: {self.hls_path}...")
        prepare_hls(input_path=self.video_out_path, output_path=self.hls_path, rewrite=rewrite)
        logger.info(f"Generated HLS stream: {self.hls_path}")

        logger.info(f"Generating Preview Image: {self.preview_image_path}...")
        generate_preview_image(input_path=self.video_out_path, output_path=self.preview_image_path, rewrite=rewrite)
        logger.info(f"Generated Preview Image: {self.preview_image_path}")

    def execute(self, rewrite=False):
        if not self.loaded:
            self.load()

        self.download_or_copy_files()
        self.process_raw_files()
        self.generate_hls_feed(rewrite=rewrite)
