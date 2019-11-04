import logging
from multiprocessing import Pool
import os
import os.path

import boto3



def load_file(spec):
    # thinking about IfModifiedSince for cached or already loaded files
    s3 = boto3.resource('s3')
    output = spec['output']
    if not os.path.exists(output):
        logging.info("loading %s from %s", spec['key'], spec['bucketName'])
        directory = os.path.dirname(output)
        os.makedirs(directory, exist_ok=True)
        s3.meta.client.download_file(spec['bucketName'], spec['key'], spec['output'])
    else:
        logging.info("%s exists", output)
    return (True, None)


def execute_manifest(manifest):
    pool = Pool(processes=6)
    return pool.map(load_file, manifest["download"])
