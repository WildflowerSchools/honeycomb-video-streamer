import os.path
import shutil

import ffmpeg

from .log import logger
from .stream_reader import NonBlockingStreamReader, StreamTimeout


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
        # Read video file, output stdout to /dev/null, allow for repeated log
        # messages, run aynchronously so we can scan output to stderr
        process_vid = (
            ffmpeg.input(video_path)
            .output("/dev/null", f="null")
            .global_args("-loglevel", "repeat")
            .run_async(pipe_stderr=True)
        )
        nb_stderr_stream = NonBlockingStreamReader(process_vid.stderr)

        last_output = ""
        repeat = 0
        repeat_threshold = 30  # Number of times to allow a repeated log message
        timeout_threshold = 1800  # Break if stderr hasn't output a msg in 30 minutes
        while True:
            output = nb_stderr_stream.readline(timeout_threshold)
            if not output:
                # Stream exhausted, file read successfully!
                return True
            logger.info(output)

            if repeat >= repeat_threshold:
                logger.warning("File read stuck in repeat loop, terminating read")
                return False

            if output == last_output:
                repeat += 1
            else:
                repeat = 0

            last_output = output
    except StreamTimeout:
        logger.warning("Stream timeout, ffmpeg hanging reading video file")
        return False
    except ffmpeg._run.Error:
        logger.error(f"video file '{video_path}' corrupt")
        return False

    return True


def probe_file(mp4_video_path):
    try:
        return ffmpeg.probe(mp4_video_path)
    except Exception as err:
        logger.error(err)
        raise err


def count_frames(mp4_video_path):
    # ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of
    # default=nokey=1:noprint_wrappers=1
    probe = probe_file(mp4_video_path)
    if probe is None or "streams" not in probe:
        err = f"ffmpeg returned unexpected response reading {mp4_video_path}"
        logger.error(err)
        raise ValueError(err)

    video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)
    return int(video_stream["nb_frames"])


def get_duration(hls_video_path):
    probe = ffmpeg.probe(hls_video_path)
    return float(probe["format"]["duration"])


def trim_video(input_path, output_path, duration=10):
    logger.info(f"Trimming video '{input_path}' down to {duration} seconds")

    use_tmp = input_path == output_path
    tmp_path = f"{input_path}.tmp"
    ffmpeg_input_path = input_path
    try:
        if use_tmp:
            shutil.copy(input_path, tmp_path)
            ffmpeg_input_path = tmp_path

        ffmpeg.input(ffmpeg_input_path, ss=0, to=duration).output(
            output_path, r=10, vframes=100
        ).overwrite_output().run()
    except ffmpeg._run.Error as e:
        logger.error(f"Failed trimming video {input_path}")
        logger.error(e)
        return False
    finally:
        if use_tmp:
            os.remove(tmp_path)

    return True


def concat_videos(input_path, output_path, thumb_path=None, rewrite=False):
    success = False

    retries = 3
    for ii in range(retries):
        if success:
            break

        try:
            concat_mp4_exists = os.path.exists(output_path)
            if concat_mp4_exists:
                if rewrite or not is_valid_video(output_path):
                    os.remove(output_path)
                    concat_mp4_exists = False

            if not concat_mp4_exists:
                files = ffmpeg.input(f"file:{input_path}", format="concat", safe=0, r=10)
                files.output(f"file:{output_path}", c="copy", r=10, vsync=0).run()
            else:
                logger.info(f"concatenated video '{output_path}' already exists")

            if thumb_path is not None:
                thumb_exists = os.path.exists(thumb_path)
                if thumb_exists:
                    if rewrite or not is_valid_video(thumb_path):
                        os.remove(thumb_path)
                        thumb_exists = False

                if not thumb_exists:
                    ffmpeg.input(output_path).filter("scale", 320, -1).output(
                        thumb_path, preset="veryfast", sws_flags="fast_bilinear", acodec="copy", crf=30
                    ).run()
                else:
                    logger.info(f"small video '{thumb_path}' already exists")

            success = True
        except ffmpeg._run.Error as e:
            logger.warning(
                f"concatenate videos failed with ffmpeg Error, tried {ii + 1}/{retries} (using rewrite=True)"
            )
            logger.warning(e)
            rewrite = True

    if not success:
        raise Exception("Failed concatenating mp4 file")


def prepare_hls(input_path, output_path, hls_time=10, rewrite=False, append=True):
    hls_exists = os.path.exists(output_path)

    if hls_exists:
        # Commenting out valid video check, great idea but is VERY SLOW:
        if rewrite:  # or not is_valid_video(output_path):
            os.remove(output_path)
            hls_exists = False

    hls_options = dict(
        format="hls",
        hls_time=hls_time,
        hls_list_size=0,
        # hls_segment_type="fmp4", # This should work better on Safari, but instead causes Safari to crash in < 20 seconds
        # movflags="+frag_keyframe",
        c="copy",
    )
    if not hls_exists:
        # ffmpeg -i ./public/videos/test/cc-1/output-small.mp4 -profile:v
        # baseline -level 3.0 -s 640x360 -start_number 0 -hls_time hls_time
        # -hls_list_size 0 -f hls public/videos/output.m3u8
        ffmpeg.input(input_path).output(output_path, **hls_options).run()
    else:
        if append:
            ffmpeg.input(input_path).output(output_path, hls_flags="append_list", **hls_options).run()
        else:
            logger.info(f"hls video '{output_path}' already exists, and append mode set to 'False'")


def generate_preview_image(input_path, output_path, rewrite=False):
    input_fps = 10
    preview_exists = os.path.exists(output_path)

    if preview_exists:
        if rewrite:
            os.remove(output_path)
            preview_exists = False

    # ffmpeg -y -i ./public/videos/test/cc-1/output.m3u8 -f image2 -vframes 1
    # preview.jpg
    if not preview_exists:
        ss = 0
        try:
            frames = count_frames(input_path)
            ss = round(frames / 2 / input_fps)
        except ValueError as e:
            logger.error(e)

        if ss > 0:
            ffmpeg.input(input_path, ss=ss).output(output_path, format="image2", vframes=1).run()
        else:
            logger.warning(f"Could not generate preview image for '{input_path}', file appears empty or corrupted")
    else:
        logger.info(f"preview image '{output_path}' already exists")


def technical_difficulties_blank_image_path():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    return f"{dir_path}/assets/blank.jpg"


def create_technical_difficulties_clip(clip_path):
    if not os.path.exists(clip_path):
        input_path = technical_difficulties_blank_image_path()
        duration = 10
        fps = 10
        clip = ffmpeg.input(input_path, loop=1, to=duration)
        # Added vframes to for 100 frames and prevent ffmpeg from adding an
        # additional 2 rogue frames
        clip.output(clip_path, r=fps, format="mp4", pix_fmt="bgr24", vframes=100).run()


def copy_technical_difficulties_clip(clip_path, output_path, rewrite=False):
    if not os.path.exists(clip_path):
        create_technical_difficulties_clip(clip_path)

    if rewrite or not os.path.exists(output_path):
        try:
            shutil.copy(clip_path, output_path)
        except shutil.SameFileError:
            pass


def pad_video(input_path, output_path, frames):
    """
    Add number of specified frames to the end of the given video.

    :param input_path: Path to video file input
    :param input_path: Path to video file output
    :param frames: Number of frames to append
    :return: boolean
    """

    logger.info(f"Padding video '{input_path}' with {frames} frames")

    use_tmp = input_path == output_path
    tmp_path = f"{input_path}.tmp"
    ffmpeg_input_path = input_path
    if frames <= 0:
        logger.warning(f"Frame padding giving to pad_video smaller than 1: {frames}")
        return False

    try:
        if use_tmp:
            shutil.copy(input_path, tmp_path)
            ffmpeg_input_path = tmp_path

        stop_duration = frames / 10
        ffmpeg.input(ffmpeg_input_path).output(
            output_path, filter_complex=f"tpad=stop_duration={stop_duration}:stop_mode=clone"
        ).overwrite_output().run()
    except ffmpeg._run.Error as e:
        logger.error(f"Failed padding {input_path} with {frames} additional frames")
        logger.error(e)
        return False
    finally:
        if use_tmp:
            os.remove(tmp_path)

    return True