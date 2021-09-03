from datetime import timedelta
import itertools
import json
import logging
import os
import os.path

import click
from dotenv import load_dotenv
import honeycomb

from .introspection import get_assignments, get_datapoint_keys_for_assignment_in_range, process_assignment_datapoints_for_download, get_environment_id
from .transcode import concat_videos, count_frames, get_duration, generate_preview_image, pad_video, prepare_hls, trim_video
from .manifest import Manifest
from .manifestations import add_classroom, add_date_to_classroom
from . import const, util


load_dotenv()


HONEYCOMB_URI = os.getenv(
    "HONEYCOMB_URI",
    "https://honeycomb.api.wildflower-tech.org/graphql")
HONEYCOMB_TOKEN_URI = os.getenv(
    "HONEYCOMB_TOKEN_URI",
    "https://wildflowerschools.auth0.com/oauth/token")
HONEYCOMB_AUDIENCE = os.getenv(
    "HONEYCOMB_AUDIENCE",
    "https://honeycomb.api.wildflowerschools.org")
HONEYCOMB_CLIENT_ID = os.getenv("HONEYCOMB_CLIENT_ID")
HONEYCOMB_CLIENT_SECRET = os.getenv("HONEYCOMB_CLIENT_SECRET")


@click.group()
@click.pass_context
def main(ctx):
    ctx.ensure_object(dict)
    if HONEYCOMB_CLIENT_ID is None:
        raise ValueError("HONEYCOMB_CLIENT_ID is required")
    if HONEYCOMB_CLIENT_SECRET is None:
        raise ValueError("HONEYCOMB_CLIENT_SECRET is required")
    ctx.obj['honeycomb_client'] = honeycomb.HoneycombClient(
        uri=HONEYCOMB_URI,
        client_credentials={
            'token_uri': HONEYCOMB_TOKEN_URI,
            'audience': HONEYCOMB_AUDIENCE,
            'client_id': HONEYCOMB_CLIENT_ID,
            'client_secret': HONEYCOMB_CLIENT_SECRET,
        }
    )


@main.command()
@click.pass_context
@click.option('--environment_name', "-e",
              help='name of the environment in honeycomb, required for using the honeycomb consumer', required=True)
@click.option('--output_path', "-o",
              help='path to output prepared videos to', required=True)
@click.option('--output_name', "-n",
              help='name to give the output video', required=True)
@click.option('--day', "-d",
              help='day of video to load expects format to be YYYY-MM-DD', required=True)
def prepare_videos_for_environment_for_day(
        ctx, environment_name, output_path, output_name, day):
    datetime_of_day = util.date_to_day_format(day)
    # prepare list of datapoints for each assignment for the time period
    # selected
    start = (datetime_of_day + timedelta(hours=13)).isoformat()
    end = (datetime_of_day + timedelta(hours=22)).isoformat()
    prepare_videos_for_environment_for_time_range(
        ctx, environment_name, output_path, output_name, start, end)


@main.command()
@click.pass_context
@click.option('--environment_name', "-e",
              help='name of the environment in honeycomb, required for using the honeycomb consumer', required=True)
@click.option('--output_path', "-o",
              help='path to output prepared videos to', required=True)
@click.option('--output_name', "-n",
              help='name to give the output video', required=True)
@click.option('--start',
              help='start time of video to load expects format to be YYYY-MM-DDTHH:MM', required=True)
@click.option('--end', help='end time of video to load expects format to be YYYY-MM-DDTHH:MM', required=True)
def list_datapoints_for_environment_for_time_range(
        ctx, environment_name, output_path, output_name, start, end):
    honeycomb_client = ctx.obj['honeycomb_client']
    # load the environment to get all the assignments
    environment_id = get_environment_id(honeycomb_client, environment_name)
    with open(f"{output_path}/{output_name}", 'w') as output_fp:
        output_fp.write(f"assignment_id,timestamp,data_id,key\n")
        # evaluate the assignments to filter out non-camera assignments
        assignments = get_assignments(honeycomb_client, environment_id)
        for assignment_id, assignment_name in assignments:
            datapoints = list(
                get_datapoint_keys_for_assignment_in_range(
                    honeycomb_client, assignment_id, start, end))
            for item in datapoints:
                output_fp.write(
                    f"{assignment_id},{item['timestamp']},{item['data_id']},{item['file']['key']}\n")
        output_fp.flush()


def vts(frames):
    total_seconds = frames // 10
    fractional = frames % 10
    total_minutes = total_seconds // 60
    hours = total_minutes // 60
    minutes = total_minutes - (hours * 60)
    seconds = total_seconds - (total_minutes * 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{fractional}00"


@main.command()
@click.pass_context
@click.option('--environment_name', "-e",
              help='name of the environment in honeycomb, required for using the honeycomb consumer', required=True)
@click.option('--output_path', "-o",
              help='path to output prepared videos to', required=True)
@click.option('--output_name', "-n",
              help='name to give the output video', required=True)
@click.option('--start',
              help='start time of video to load expects format to be YYYY-MM-DDTHH:MM', required=True)
@click.option('--end', help='end time of video to load expects format to be YYYY-MM-DDTHH:MM', required=True)
@click.option('--rewrite', help='rewrite any generated images/video (i.e. hls feeds) (already downloaded raw videos are not destroyed or re-downloaded)', is_flag=True, default=False)
@click.option('--append', help='append images/video to HLS feed (start time for given day must align)',
              is_flag=True, default=False)
def prepare_videos_for_environment_for_time_range(
        ctx, environment_name, output_path, output_name, start, end, rewrite, append):
    if rewrite:
        logging.warning(
            "Rewrite flag enabled! All generated images/video will be recreated.")
    elif append:
        logging.warning(
            "If existing video is discovered, new video will be appended")

    honeycomb_client = ctx.obj['honeycomb_client']
    # load the environment to get all the assignments
    environment_id = get_environment_id(honeycomb_client, environment_name)
    add_classroom(output_path, environment_name, environment_id)

    # prep this output's environment index.json manifest file
    # this index will point to each camera's HLS and thumbnail assets
    manifest_path = os.path.join(
        output_path,
        environment_id,
        output_name,
        "index.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

    index_manifest = {}
    if not os.path.isfile(manifest_path):
        rewrite = True
    else:
        with open(manifest_path, 'r') as fp:
            try:
                index_manifest = json.load(fp)
            except ValueError as e:
                logging.error(
                    "Failed loading {} - {}".format(index_manifest, e))
                rewrite = True

    # track video json to write to environment's index.json
    all_video_meta = index_manifest.get('videos', [])

    # evaluate the assignments to filter out non-camera assignments
    assignments = get_assignments(honeycomb_client, environment_id)
    for idx, (assignment_id, assignment_name) in enumerate(assignments):
        rewrite_current = rewrite
        datapoints = list(
            get_datapoint_keys_for_assignment_in_range(
                honeycomb_client, assignment_id, start, end))

        logging.info(
            "%s has %i in %s=%s",
            assignment_name,
            len(datapoints),
            start,
            end)
        if len(datapoints) == 0:
            logging.warning(
                "No videos for assignment: '{}':{}".format(
                    assignment_id, assignment_name))

        # fetch all of the videos for each camera, records are returned ordered by timestamp
        # missing clips are stored behind the "missing" attribute
        manifest = process_assignment_datapoints_for_download(target=f"{output_path}/{environment_id}/{output_name}/{assignment_name}/",
                                                              datapoints=datapoints,
                                                              start=start,
                                                              end=end,
                                                              manifest=Manifest(rtrim=True))
        if len(manifest.get_files()) == 0:
            continue

        manifest.execute(
            empty_clip_path=const.empty_clip_path(output_path),
            rewrite=rewrite_current)

        camera_specific_directory = os.path.join(
            output_path, environment_id, output_name, assignment_name)
        hls_out = os.path.join(camera_specific_directory, "output.m3u8")
        hls_thumb_out = os.path.join(
            camera_specific_directory,
            "output-small.m3u8")
        preview_image_out = os.path.join(
            camera_specific_directory, "output-preview.jpg")
        preview_image_thumb_out = os.path.join(
            camera_specific_directory, "output-preview-small.jpg")
        camera_video_history_path = os.path.join(
            camera_specific_directory, "history.json")

        last_end_time = start
        camera_video_history = []
        if not os.path.isfile(camera_video_history_path):
            rewrite_current = True
        else:
            with open(camera_video_history_path, 'r') as fp:
                try:
                    camera_video_history = json.load(fp)
                except ValueError as e:
                    logging.error(
                        "Failed loading {} - {}".format(camera_video_history_path, e))
                    rewrite_current = True

            is_valid_history = camera_video_history is not None and isinstance(
                camera_video_history, list)
            is_valid_and_has_history = is_valid_history and len(
                camera_video_history) > 0

            if not is_valid_history:
                camera_video_history = []
                rewrite_current = True

            elif is_valid_and_has_history:
                camera_start_time = camera_video_history[0]['start_time']
                camera_end_time = camera_video_history[-1]['end_time']
                if util.str_to_date(index_manifest['start']) != util.str_to_date(
                        camera_start_time):
                    logger.error(
                        "Unexpected start_time for camera '{}': {} != {}. Recreating HLS stream...".format(
                            assignment_name, camera_start_time, index_manifest['start']))
                    camera_video_history = []
                    rewrite_current = True
                else:
                    expected_duration = (
                        util.str_to_date(camera_end_time) -
                        util.str_to_date(camera_start_time)).total_seconds()
                    actual_duration = get_duration(hls_out)
                    if actual_duration != expected_duration:
                        logger.error(
                            "Unexpected duration for camera '{}': {} != {}. Recreating HLS stream...".format(
                                assignment_name, expected_duration, actual_duration))
                        camera_video_history = []
                        rewrite_current = True

                for record in camera_video_history:
                    if last_end_time is None:
                        last_end_time = util.date_to_video_history_format(
                            record['end_time'])
                    else:
                        if util.str_to_date(
                                record['end_time']) > util.str_to_date(last_end_time):
                            last_end_time = util.date_to_video_history_format(
                                record['end_time'])

        current_input_files_path = os.path.join(
            camera_specific_directory,
            f"files_{len(camera_video_history)}.txt")
        video_out_path = os.path.join(
            camera_specific_directory,
            f"output_{len(camera_video_history)}.mp4")
        thumb_out_path = os.path.join(
            camera_specific_directory,
            f"output-small_{len(camera_video_history)}.mp4")

        current_video_history = {
            "start_time": last_end_time,
            "end_time": None,
            "files": [],
            "video_out_path": video_out_path,
            "thumb_out_path": thumb_out_path
        }

        already_processed_files = list(
            map(lambda x: x['files'], camera_video_history))
        already_processed_files = list(
            itertools.chain(*already_processed_files))

        with open(current_input_files_path, 'w') as fp:
            count = 0
            for file in sorted(manifest.get_files(),
                               key=lambda x: x['output']):
                line = file['output']
                # Skip video files that have already been processed
                if line in already_processed_files:
                    continue

                # Process new video files
                current_video_history['files'].append(line)
                # '2021-04-15T13:00:00.000Z.video.mp4'
                file_name = os.path.basename(line)

                if current_video_history['end_time'] is None or \
                        file['end'] > util.str_to_date(current_video_history['end_time']):
                    current_video_history['end_time'] = util.date_to_video_history_format(
                        file['end'])

                num_frames = count_frames(line)
                if num_frames < 100 and num_frames > 97:
                    pad_video(line, line, frames=(100 - num_frames))
                    num_frames == 100
                if num_frames == 101:
                    trim_video(line, line)
                    num_frames == 100

                fp.write(f"file \'file:{camera_specific_directory}/")
                fp.write(file_name)
                fp.write(
                    f"\' duration 00:00:{util.format_frames(num_frames)} inpoint {vts(count)} outpoint {vts(count + num_frames)}\n")
                count += num_frames
            fp.flush()

        if len(current_video_history['files']) > 0:
            concat_videos(
                current_input_files_path,
                video_out_path,
                thumb_path=thumb_out_path,
                rewrite=True)

            # prepare videos for HLS streaming
            prepare_hls(
                video_out_path,
                hls_out,
                rewrite=rewrite_current,
                append=append)
            prepare_hls(
                thumb_out_path,
                hls_thumb_out,
                rewrite=rewrite_current,
                append=append)

            camera_video_history.append(
                current_video_history
            )

            generate_preview_image(hls_out, preview_image_out)
            generate_preview_image(hls_thumb_out, preview_image_thumb_out)

        current_video_meta = {
            "device_id": assignment_id,
            "device_name": assignment_name,
            "url": f"/videos/{environment_id}/{output_name}/{assignment_name}/output.m3u8",
            "preview_url": f"/videos/{environment_id}/{output_name}/{assignment_name}/output-preview.jpg",
            "preview_thumbnail_url": f"/videos/{environment_id}/{output_name}/{assignment_name}/output-preview-small.jpg",
        }

        ######
        # Update or append to the video_meta data object
        ######
        updated_existing_video_meta_record = False
        for idx, meta_record in enumerate(all_video_meta):
            if meta_record['device_id'] == assignment_id:
                updated_existing_video_meta_record = True
                all_video_meta[idx] = current_video_meta
                break

        if not updated_existing_video_meta_record:
            all_video_meta.append(current_video_meta)
        ######

        with open(camera_video_history_path, 'w') as fp:
            json.dump(camera_video_history, fp)
            fp.flush()

        # Add a record in the classroom's index that points to this run's video
        # feeds
        add_date_to_classroom(output_path, environment_id,
                              start[:10], output_name, [start[11:], end[11:]])

        with open(manifest_path, 'w') as fp:
            json.dump({"start": start,
                       "end": end,
                       "videos": all_video_meta,
                       "building": (idx < len(assignments) - 1)
                       }, fp)
            fp.flush()
            # done


if __name__ == '__main__':
    logger = logging.getLogger()

    logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    main(auto_envvar_prefix="HONEYCOMB")
