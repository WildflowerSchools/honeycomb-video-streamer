import logging
import os
import os.path

import ffmpeg


def concat_videos(input_path, output_path, thumb_path=None):
    if not os.path.exists(output_path):
        files = ffmpeg.input(input_path, format='concat', safe=0)
        files.output(output_path, c='copy').run()
    else:
        logging.info("concatenated video already exists")
    if thumb_path is not None and not os.path.exists(thumb_path):
        ffmpeg.input(output_path).filter('scale', 320, -1).output(thumb_path).run()
    else:
        logging.info("small video already exists")


# ffmpeg -f concat -i ./public/videos/test/cc-1/files.txt one_love.mp4

if __name__ == '__main__':
    concat_videos("./public/videos/test/cc-1/files.txt", "test.mp4")


# ffmpeg -i ./public/videos/test/cc-1/output-small.mp4 -profile:v baseline -level 3.0 -s 640x360 -start_number 0 -hls_time 10 -hls_list_size 0 -f hls public/videos/output.m3u8
