import logging
import os
from multiprocessing import Pool

import boto3

from .transcode import copy_technical_difficulties_clip
from . import util


class Manifest(object):
    def __init__(self, rtrim=False):
        self.rtrim = rtrim
        self.remote_video_list = []
        self.missing_video_list = []

    def get_files(self):
        last_available_video_end_time = None
        if self.rtrim:
            last_available_video_end_time = self.get_last_valid_clip_end_time()

        files = []
        for d in self.remote_video_list:
            files.append({
                "output": d["output"],
                "start": d["start"],
                "end": d["end"]
            })

        for m in self.missing_video_list:
            if last_available_video_end_time is not None and m['start'] < last_available_video_end_time:
                files.append({
                    "output": m["output"],
                    "start": m["start"],
                    "end": m["end"]
                })

        return files

    def add_to_download(self, bucketName, key, output, start, end):
        self.remote_video_list.append({
            "bucketName": bucketName,
            "key": key,
            "output": output,
            "start": util.str_to_date(start),
            "end": util.str_to_date(end)})

    def add_to_missing(self, output, start, end):
        self.missing_video_list.append({
            "output": output,
            "start": util.str_to_date(start),
            "end": util.str_to_date(end)})

    def get_last_valid_clip_end_time(self):
        last_available_video_end_time = None
        if len(self.remote_video_list) > 0:
            last_available_video_end_time = self.remote_video_list[-1]["end"]

        return last_available_video_end_time

    def download_file(self, spec):
        # thinking about IfModifiedSince for cached or already loaded files
        s3 = boto3.resource('s3')
        output = spec['output']
        if not os.path.exists(output):
            logging.info("loading %s from %s", spec['key'], spec['bucketName'])
            util.create_dir(output)
            s3.meta.client.download_file(
                spec['bucketName'], spec['key'], spec['output'])
        else:
            logging.info("%s exists", output)
        return (True, None)

    def execute(self, empty_clip_path, rewrite=False):
        last_available_video_end_time = None
        if self.rtrim:
            last_available_video_end_time = self.get_last_valid_clip_end_time()

        for missing in self.missing_video_list:
            output_path = missing['output']
            if last_available_video_end_time is not None and missing[
                    "start"] < last_available_video_end_time:
                util.create_dir(output_path)
                copy_technical_difficulties_clip(
                    empty_clip_path, output_path, rewrite)

        pool = Pool(processes=6)
        return pool.map(self.download_file, self.remote_video_list)
