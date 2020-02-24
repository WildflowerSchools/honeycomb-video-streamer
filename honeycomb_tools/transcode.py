import logging
import os.path

import ffmpeg


def trim_video(input_path, output_path, duration=10):
    if not os.path.exists(output_path):
        trim = ffmpeg.input(input_path, ss=0, to=duration)
        trim.output(output_path, c="copy", r=10).run()


def concat_videos(input_path, output_path, thumb_path=None):
    # TODO handle timescale issues due to missing chunks or replaced chunks
    if not os.path.exists(output_path):
        files = ffmpeg.input(input_path, format='concat', safe=0, r=10)
        files.output(output_path, c="copy", r=10, vsync=0).run()
    else:
        logging.info("concatenated video already exists")
    if thumb_path is not None and not os.path.exists(thumb_path):
        ffmpeg.input(output_path).filter('scale', 320, -1).output(thumb_path).run()
    else:
        logging.info("small video already exists")


def prepare_hls(input_path, output_path, hls_time=10):
    # ffmpeg -i ./public/videos/test/cc-1/output-small.mp4 -profile:v baseline -level 3.0 -s 640x360 -start_number 0 -hls_time 10 -hls_list_size 0 -f hls public/videos/output.m3u8
    ffmpeg.input(input_path).output(output_path, format="hls", hls_list_size=0, c="copy").run()
