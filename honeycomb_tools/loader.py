import logging
from multiprocessing import Pool
import os
import os.path

import boto3

from .transcode import copy_technical_difficulties_clip


def create_dir(dir_path):
    directory = os.path.dirname(dir_path)
    os.makedirs(directory, exist_ok=True)


def load_file(spec):
    # thinking about IfModifiedSince for cached or already loaded files
    s3 = boto3.resource('s3')
    output = spec['output']
    if not os.path.exists(output):
        logging.info("loading %s from %s", spec['key'], spec['bucketName'])
        create_dir(output)
        s3.meta.client.download_file(spec['bucketName'], spec['key'], spec['output'])
    else:
        logging.info("%s exists", output)
    return (True, None)


def execute_manifest(manifest, empty_clip_path, rewrite=False):
    for missing in manifest['missing']:
        output_path = missing['output']
        create_dir(output_path)
        copy_technical_difficulties_clip(empty_clip_path, output_path, rewrite)

    pool = Pool(processes=6)
    return pool.map(load_file, manifest["download"])
