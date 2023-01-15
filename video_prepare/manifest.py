import copy
import os
from multiprocessing import cpu_count
import shutil
import tempfile

import video_io

from . import util
from .log import logger


class Manifest:
    def __init__(self, output_directory="", empty_clip_path=""):
        self.captured_video_list = []
        self.missing_video_list = []
        self.downloaded_video_list = []
        self.output_directory = output_directory
        self.empty_clip_path = empty_clip_path

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

    def download_files(self, workers=cpu_count() - 1):
        downloadable_video_list = []
        for video in self.captured_video_list:
            if not os.path.exists(video["video_streamer_path"]):
                util.create_dir(self.output_directory)
                downloadable_video_list.append(video)

        with tempfile.TemporaryDirectory() as tmp_dir:
            videos = video_io.download_video_files(
                video_metadata=downloadable_video_list, local_video_directory=tmp_dir, max_workers=workers
            )

            for downloaded_file in downloadable_video_list:
                try:
                    shutil.move(downloaded_file["video_local_path"], downloaded_file["video_streamer_path"])
                except Exception as ex:
                    err = f"Failed copying downloaded video '{downloaded_file['video_local_path']}' to final storage path '{downloaded_file['video_streamer_path']}'"
                    logger.error(err)
                    raise ex

            return videos

    def execute(self):
        return self.download_files()
