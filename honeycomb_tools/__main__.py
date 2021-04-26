from datetime import datetime, timedelta
from dateutil.parser import parse as date_time_parse
import itertools
import json
import logging
import os
import os.path

import click
from dotenv import load_dotenv
import honeycomb

from honeycomb_tools.introspection import get_assignments, get_datapoint_keys_for_assignment_in_range, process_assignment_datapoints_for_download, get_environment_id
from honeycomb_tools.loader import execute_manifest
from honeycomb_tools.transcode import concat_videos, count_frames, get_duration, generate_preview_image, pad_video, prepare_hls, trim_video
from honeycomb_tools.manifestations import add_classroom, add_date_to_classroom


load_dotenv()


HONEYCOMB_URI = os.getenv("HONEYCOMB_URI", "https://honeycomb.api.wildflower-tech.org/graphql")
HONEYCOMB_TOKEN_URI = os.getenv("HONEYCOMB_TOKEN_URI", "https://wildflowerschools.auth0.com/oauth/token")
HONEYCOMB_AUDIENCE = os.getenv("HONEYCOMB_AUDIENCE", "https://honeycomb.api.wildflowerschools.org")
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
@click.option('--environment_name', "-e", help='name of the environment in honeycomb, required for using the honeycomb consumer', required=True)
@click.option('--output_path', "-o", help='path to output prepared videos to', required=True)
@click.option('--output_name', "-n", help='name to give the output video', required=True)
@click.option('--day', "-d", help='day of video to load expects format to be YYYY-MM-DD', required=True)
def prepare_videos_for_environment_for_day(ctx, environment_name, output_path, output_name, day):
    datetime_of_day = parse_day(day)
    # prepare list of datapoints for each assignment for the time period selected
    start = (datetime_of_day + timedelta(hours=13)).isoformat()
    end = (datetime_of_day + timedelta(hours=22)).isoformat()
    prepare_videos_for_environment_for_time_range(ctx, environment_name, output_path, output_name, start, end)


@main.command()
@click.pass_context
@click.option('--environment_name', "-e", help='name of the environment in honeycomb, required for using the honeycomb consumer', required=True)
@click.option('--output_path', "-o", help='path to output prepared videos to', required=True)
@click.option('--output_name', "-n", help='name to give the output video', required=True)
@click.option('--start', help='start time of video to load expects format to be YYYY-MM-DDTHH:MM', required=True)
@click.option('--end', help='end time of video to load expects format to be YYYY-MM-DDTHH:MM', required=True)
def list_datapoints_for_environment_for_time_range(ctx, environment_name, output_path, output_name, start, end):
    honeycomb_client = ctx.obj['honeycomb_client']
    # load the environment to get all the assignments
    environment_id = get_environment_id(honeycomb_client, environment_name)
    with open(f"{output_path}/{output_name}", 'w') as output_fp:
        output_fp.write(f"assignment_id,timestamp,data_id,key\n")
        # evaluate the assignments to filter out non-camera assignments
        assignments = get_assignments(honeycomb_client, environment_id)
        for assignment_id, assignment_name in assignments:
            datapoints = list(get_datapoint_keys_for_assignment_in_range(honeycomb_client, assignment_id, start, end))
            for item in datapoints:
                output_fp.write(f"{assignment_id},{item['timestamp']},{item['data_id']},{item['file']['key']}\n")
        output_fp.flush()


def vts(index):
    return f"{(int(int(index/6)/60)):02}:{int(index/6) % 60:02}:{(index % 6) * 10:02}.000"


@main.command()
@click.pass_context
@click.option('--environment_name', "-e", help='name of the environment in honeycomb, required for using the honeycomb consumer', required=True)
@click.option('--output_path', "-o", help='path to output prepared videos to', required=True)
@click.option('--output_name', "-n", help='name to give the output video', required=True)
@click.option('--start', help='start time of video to load expects format to be YYYY-MM-DDTHH:MM', required=True)
@click.option('--end', help='end time of video to load expects format to be YYYY-MM-DDTHH:MM', required=True)
@click.option('--rewrite', help='rewrite any generated images/video (i.e. hls feeds) (already downloaded raw videos are not destroyed or re-downloaded)', is_flag=True, default=False)
@click.option('--append', help='append images/video to HLS feed (start time for given day must align)', is_flag=True, default=False)
def prepare_videos_for_environment_for_time_range(ctx, environment_name, output_path, output_name, start, end, rewrite, append):
    if rewrite:
        logging.warning("Rewrite flag enabled! All generated images/video will be recreated.")
    elif append:
        logging.warning("If existing video is discovered, new video will be appended")

    honeycomb_client = ctx.obj['honeycomb_client']
    # load the environment to get all the assignments
    environment_id = get_environment_id(honeycomb_client, environment_name)
    add_classroom(output_path, environment_name, environment_id)

    # prep this output's environment index.json manifest file
    # this index will point to each camera's HLS and thumbnail assets
    manifest_path = os.path.join(output_path, environment_id, output_name, "index.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

    index_manifest = {}
    with open(manifest_path, 'r') as fp:
        try:
            index_manifest = json.load(fp)
        except ValueError as e:
            logging.error("Failed loading {} - {}".format(index_manifest, e))
            rewrite = True

    # track video json to write to environment's index.json
    all_video_meta = index_manifest.get('videos', [])

    # evaluate the assignments to filter out non-camera assignments
    assignments = get_assignments(honeycomb_client, environment_id)
    for idx, (assignment_id, assignment_name) in enumerate(assignments):
        rewrite_current = rewrite
        datapoints = list(get_datapoint_keys_for_assignment_in_range(honeycomb_client, assignment_id, start, end))

        logging.info("%s has %i in %s=%s", assignment_name, len(datapoints), start, end)
        if len(datapoints) == 0:
            logging.warning("No videos for assignment: '{}':{}".format(assignment_id, assignment_name))

        # fetch all of the videos for each camera
        download_manifest = process_assignment_datapoints_for_download(f"{output_path}/{environment_id}/{output_name}/{assignment_name}/", datapoints, start, end)

        empty_clip_path = os.path.join(output_path, "empty_frames.video.mp4")

        execute_manifest(download_manifest, empty_clip_path, rewrite_current)
        if len(download_manifest["files"]) == 0:
            continue

        camera_specific_directory = os.path.join(output_path, environment_id, output_name, assignment_name)

        hls_out = os.path.join(camera_specific_directory, "output.m3u8")
        hls_thumb_out = os.path.join(camera_specific_directory, "output-small.m3u8")
        preview_image_out = os.path.join(camera_specific_directory, "output-preview.jpg")
        preview_image_thumb_out = os.path.join(camera_specific_directory, "output-preview-small.jpg")
        camera_video_history_path = os.path.join(camera_specific_directory, "history.json")

        last_end_time = start
        camera_video_history = []
        if not os.path.isfile(camera_video_history_path):
            rewrite_current = True
        else:
            with open(camera_video_history_path, 'r') as fp:
                try:
                    camera_video_history = json.load(fp)
                except ValueError as e:
                    logging.error("Failed loading {} - {}".format(camera_video_history_path, e))
                    rewrite_current = True

            is_valid_history = camera_video_history is not None and isinstance(camera_video_history, list)
            is_valid_and_has_history = is_valid_history and len(camera_video_history) > 0

            if not is_valid_history:
                camera_video_history = []
                rewrite_current = True

            elif is_valid_and_has_history:
                camera_start_time = camera_video_history[0]['start_time']
                camera_end_time = camera_video_history[-1]['end_time']
                if date_time_parse(index_manifest['start']) != date_time_parse(camera_start_time):
                    logger.error("Unexpected start_time for camera '{}': {} != {}. Recreating HLS stream...".format(assignment_name, camera_start_time, index_manifest['start']))
                    camera_video_history = []
                    rewrite_current = True
                elif date_time_parse(index_manifest['end']) != date_time_parse(camera_end_time):
                    logger.error("Unexpected end_time for camera '{}': {} != {}. Recreating HLS stream...".format(assignment_name, camera_end_time, index_manifest['end']))
                    camera_video_history = []
                    rewrite_current = True
                else:
                    expected_duration = (date_time_parse(camera_end_time) - date_time_parse(camera_start_time)).total_seconds()
                    actual_duration = get_duration(hls_out)
                    if actual_duration != expected_duration:
                        logger.error("Unexpected duration for camera '{}': {} != {}. Recreating HLS stream...".format(assignment_name, expected_duration, actual_duration))
                        camera_video_history = []
                        rewrite_current = True

                for record in camera_video_history:
                    if last_end_time is None:
                        last_end_time = record['end_time']
                    else:
                        if date_time_parse(record['end_time']) > date_time_parse(last_end_time):
                            last_end_time = record['end_time']

        current_input_files_path = os.path.join(camera_specific_directory, f"files_{len(camera_video_history)}.txt")
        video_out_path = os.path.join(camera_specific_directory, f"output_{len(camera_video_history)}.mp4")
        thumb_out_path = os.path.join(camera_specific_directory, f"output-small_{len(camera_video_history)}.mp4")

        current_video_history = {
            "start_time": last_end_time,
            "end_time": None,
            "files": [],
            "video_out_path": video_out_path,
            "thumb_out_path": thumb_out_path
        }

        already_processed_files = list(map(lambda x: x['files'], camera_video_history))
        already_processed_files = list(itertools.chain(*already_processed_files))

        with open(current_input_files_path, 'w') as fp:
            count = 0
            for file in sorted(download_manifest["files"], key=lambda x: x['output']):
                line = file['output']
                # Skip video files that have already been processed
                if line in already_processed_files:
                    continue

                # Process new video files
                current_video_history['files'].append(line)
                file_name = os.path.basename(line)  # '2021-04-15T13:00:00.000Z.video.mp4'
                file_start_time = datetime.fromisoformat(file['start'].rstrip('Z'))
                file_end_time = file_start_time + timedelta(0, 10)

                if current_video_history['end_time'] is None or \
                    file_end_time > datetime.fromisoformat(current_video_history['end_time'].rstrip('Z')):
                    current_video_history['end_time'] = file_end_time.isoformat(sep=' ', timespec='milliseconds')

                num_frames = count_frames(line)
                if num_frames < 100:
                    pad_video(line, line, frames=(100 - num_frames))
                elif num_frames > 100:
                    trim_video(line, line)

                fp.write(f"file \'file:{camera_specific_directory}/")
                fp.write(file_name)
                fp.write(f"\' duration 00:00:10.000 inpoint {vts(count)} outpoint {vts(count + 1)}\n")
                count += 1
            fp.flush()

        if len(current_video_history['files']) > 0:
            concat_videos(current_input_files_path, video_out_path, thumb_path=thumb_out_path, rewrite=rewrite_current)

            # prepare videos for HLS streaming
            prepare_hls(video_out_path, hls_out, rewrite=rewrite_current, append=append)
            prepare_hls(thumb_out_path, hls_thumb_out, rewrite=rewrite_current, append=append)

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

        # Add a record in the classroom's index that points to this run's video feeds
        add_date_to_classroom(output_path, environment_id, start[:10], output_name, [start[11:], end[11:]])

        with open(manifest_path, 'w') as fp:
            json.dump({
                          "start": start,
                          "end": end,
                          "videos": all_video_meta,
                          "building": (idx < len(assignments) - 1)
                        }, fp)
            fp.flush()
            # done


def parse_day(day):
    return datetime.strptime(day, "%Y-%m-%d")


if __name__ == '__main__':
    logger = logging.getLogger()

    logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    main(auto_envvar_prefix="HONEYCOMB")
