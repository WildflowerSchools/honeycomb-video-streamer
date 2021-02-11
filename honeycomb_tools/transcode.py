import logging
import os.path
import shutil

import ffmpeg

from honeycomb_tools.stream_reader import NonBlockingStreamReader, StreamTimeout


def is_valid_video(video_path):
    """
    Validate integrity of a video file. Include stream output reader to catch issue
    with ffmpeg hanging when reading corrupted HLS video file.

    TODO: Consider replacing the repeat_threshold logic with explicit check for repeated log msg that suggest HLS is stuck: "Skip ('#EXT-X-VERSION:3')\n"
    TODO: Tweak timeout_threshold to find better balance between allowing time for file to be fully scanned and time to assume file read is simply stuck

    :param video_path: Absolute/relative path to video
    :return: boolean
    """
    try:
        # Read video file, output stdout to /dev/null, allow for repeated log messages, run aynchronously so we can scan output to stderr
        process_vid = ffmpeg.input(video_path).output("/dev/null", f="null").global_args('-loglevel', 'repeat').run_async(pipe_stderr=True)
        nb_stderr_stream = NonBlockingStreamReader(process_vid.stderr)

        last_output = ''
        repeat = 0
        repeat_threshold = 30  # Number of times to allow a repeated log message
        timeout_threshold = 1800  # Break if stderr hasn't output a msg in 30 minutes
        while True:
            output = nb_stderr_stream.readline(timeout_threshold)
            if not output:
                # Stream exhausted, file read successfully!
                return True
            logging.info(output)

            if repeat >= repeat_threshold:
                logging.warning('File read stuck in repeat loop, terminating read')
                return False

            if output == last_output:
                repeat += 1
            else:
                repeat = 0

            last_output = output
    except StreamTimeout:
        logging.warning('Stream timeout, ffmpeg hanging reading video file')
        return False
    except ffmpeg._run.Error:
        logging.error("video file '{}' corrupt".format(video_path))
        return False

    return True


def count_frames(video_path):
    # ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of default=nokey=1:noprint_wrappers=1
    probe = ffmpeg.probe(video_path)
    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    return int(video_stream['nb_frames'])


def trim_video(input_path, output_path, duration=10):
    logging.info("Trimming video '{}' down to {} seconds".format(input_path, duration))

    try:
        if input_path == output_path:
            input_path = "{}.tmp".format(input_path)
            shutil.copy(output_path, input_path)

        ffmpeg.input(input_path, ss=0, to=duration).output(output_path, r=10, vframes=100).overwrite_output().run()
    except ffmpeg._run.Error as e:
        logging.error("Failed trimming video {}".format(input_path))
        logging.error(e)
        return False

    return True


def concat_videos(input_path, output_path, thumb_path=None, rewrite=False):
    retries = 3
    for ii in range(retries):
        try:
            concat_mp4_exists = os.path.exists(output_path)
            if concat_mp4_exists:
                if rewrite or not is_valid_video(output_path):
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
                    if rewrite or not is_valid_video(thumb_path):
                        os.remove(thumb_path)
                        thumb_exists = False

                if not thumb_exists:
                    ffmpeg.input(output_path).filter('scale', 320, -1).output(thumb_path, preset='veryfast').run()
                else:
                    logging.info("small video '{}' already exists".format(thumb_path))

                break
        except ffmpeg._run.Error as e:
            logging.warning("concatenate videos failed with ffmpeg Error, trying {}/{} (using rewrite=True)".format(ii, retries))
            logging.warning(e)
            rewrite = True


def prepare_hls(input_path, output_path, hls_time=10, rewrite=False):
    hls_exists = os.path.exists(output_path)

    if hls_exists:
        if rewrite or not is_valid_video(output_path):
            os.remove(output_path)
            hls_exists = False

    if not hls_exists:
        # ffmpeg -i ./public/videos/test/cc-1/output-small.mp4 -profile:v baseline -level 3.0 -s 640x360 -start_number 0 -hls_time 10 -hls_list_size 0 -f hls public/videos/output.m3u8
        ffmpeg.input(input_path).output(output_path, format="hls", hls_list_size=0, c="copy").run()
    else:
        logging.info("hls video '{}' already exists".format(output_path))


def generate_preview_image(input_path, output_path, rewrite=False):
    preview_exists = os.path.exists(output_path)

    if preview_exists:
        if rewrite:
            os.remove(output_path)
            preview_exists = False

    # ffmpeg -y -i ./public/videos/test/cc-1/output.m3u8 -f image2 -vframes 1 preview.jpg
    if not preview_exists:
        ffmpeg.input(input_path).output(output_path, format="image2", vframes=1).run()
    else:
        logging.info("preview image '{}' already exists".format(output_path))


def technical_difficulties_blank_image_path():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    return "{}/assets/blank.jpg".format(dir_path)


def create_technical_difficulties_clip(clip_path):
    if not os.path.exists(clip_path):
        input_path = technical_difficulties_blank_image_path()
        duration = 10
        fps = 10
        clip = ffmpeg.input(input_path, loop=1, to=duration)
        # Added vframes to for 100 frames and prevent ffmpeg from adding an additional 2 rogue frames
        clip.output(clip_path, r=fps, format='mp4', pix_fmt='bgr24', vframes=100).run()


def copy_technical_difficulties_clip(clip_path, output_path, rewrite=False):
    if not os.path.exists(clip_path):
        create_technical_difficulties_clip(clip_path)

    if rewrite or not os.path.exists(output_path):
        shutil.copy(clip_path, output_path)


def pad_video(input_path, output_path, frames):
    """
    Add number of specified frames to the end of the given video.

    :param input_path: Path to video file input
    :param input_path: Path to video file output
    :param frames: Number of frames to append
    :return: boolean
    """

    logging.info("Padding video '{}' with {} frames".format(input_path, frames))

    if frames <= 0:
        logging.warning("Frame padding giving to pad_video smaller than 1: {}".format(frames))
        return False

    try:
        if input_path == output_path:
            input_path = "{}.tmp".format(input_path)
            shutil.copy(output_path, input_path)

        stop_duration = frames / 10
        ffmpeg.input(input_path).output(output_path, filter_complex="tpad=stop_duration={}:stop_mode=clone".format(stop_duration)).overwrite_output().run()
    except ffmpeg._run.Error as e:
        logging.error("Failed padding {} with {} additional frames".format(input_path, frames))
        logging.error(e)
        return False

    return True