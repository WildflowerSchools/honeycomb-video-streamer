import logging
import os.path

import ffmpeg


def is_valid_video(video_path):
    try:
        ffmpeg.input(video_path).output("null", f="null").run()
    except ffmpeg._run.Error:
        logging.error("video file '{}' corrupt".format(video_path))
        return False
    else:
        return True


def trim_video(input_path, output_path, duration=10):
    if not os.path.exists(output_path):
        trim = ffmpeg.input(input_path, ss=0, to=duration)
        trim.output(output_path, c="copy", r=10).run()


def concat_videos(input_path, output_path, thumb_path=None, replace=False):
    retries = 3
    for ii in range(retries):
        try:
            concat_mp4_exists = os.path.exists(output_path)
            if concat_mp4_exists:
                if replace or not is_valid_video(output_path):
                    os.remove(output_path)
                    concat_mp4_exists = False

            if not concat_mp4_exists:
                files = ffmpeg.input(input_path, format='concat', safe=0, r=10)
                files.output(output_path, c="copy", r=10, vsync=0).run()
            else:
                logging.info("concatenated video '{}' already exists".format(output_path))

            if thumb_path is not None:
                thumb_exists = os.path.exists(thumb_path)
                if thumb_exists:
                    if replace or not is_valid_video(thumb_path):
                        os.remove(thumb_path)
                        thumb_exists = False

                if not thumb_exists:
                    ffmpeg.input(output_path).filter('scale', 320, -1).output(thumb_path).run()
                else:
                    logging.info("small video '{}' already exists".format(thumb_path))

                break
        except ffmpeg._run.Error as e:
            logging.warning("concatenate videos failed with ffmpeg Error, trying {}/{} (using replace=True)".format(ii, retries))
            logging.warning(e)
            replace = True

def prepare_hls(input_path, output_path, hls_time=10, replace=False):
    hls_exists = os.path.exists(output_path)

    if hls_exists:
        if replace or not is_valid_video(output_path):
            os.remove(output_path)
            hls_exists = False

    if not hls_exists:
        # ffmpeg -i ./public/videos/test/cc-1/output-small.mp4 -profile:v baseline -level 3.0 -s 640x360 -start_number 0 -hls_time 10 -hls_list_size 0 -f hls public/videos/output.m3u8
        ffmpeg.input(input_path).output(output_path, format="hls", hls_list_size=0, c="copy").run()
    else:
        logging.info("hls video '{}' already exists".format(output_path))


def generate_preview_image(input_path, output_path):
    # ffmpeg -y -i ./public/videos/test/cc-1/output.m3u8 -f image2 -vframes 1 preview.jpg
    if not os.path.exists(output_path):
        ffmpeg.input(input_path).output(output_path, format="image2", vframes=1).run()
    else:
        logging.info("preview image '{}' already exists".format(output_path))
