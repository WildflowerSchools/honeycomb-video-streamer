import logging
import os.path

import ffmpeg


def concat_videos(input_path, output_path, thumb_path=None):
    # TODO handle timescale issues due to missing chunks or replaced chunks
    if not os.path.exists(output_path):
        files = ffmpeg.input(input_path, format='concat', safe=0)
        files.output(output_path, c="copy").run()
    else:
        logging.info("concatenated video already exists")
    if thumb_path is not None and not os.path.exists(thumb_path):
        ffmpeg.input(output_path).filter('scale', 320, -1).output(thumb_path).run()
    else:
        logging.info("small video already exists")


def prepare_hls(input_path, output_path, hls_time=10):
    # ffmpeg -i ./public/videos/test/cc-1/output-small.mp4 -profile:v baseline -level 3.0 -s 640x360 -start_number 0 -hls_time 10 -hls_list_size 0 -f hls public/videos/output.m3u8
    ffmpeg.input(input_path).output(output_path, format="hls", c="copy").run()
