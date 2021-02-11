from datetime import datetime, timedelta
import json
import logging
import os
import os.path

import click
from dotenv import load_dotenv
import honeycomb

from honeycomb_tools.introspection import get_assignments, get_datapoint_keys_for_assignment_in_range, process_assignment_datapoints_for_download, get_environment_id
from honeycomb_tools.loader import execute_manifest
from honeycomb_tools.transcode import concat_videos, count_frames, generate_preview_image, pad_video, prepare_hls, trim_video
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
def prepare_videos_for_environment_for_time_range(ctx, environment_name, output_path, output_name, start, end, rewrite):
    if rewrite:
        logging.warning("Rewrite flag enabled! All generated images/video will be recreated.")

    honeycomb_client = ctx.obj['honeycomb_client']
    # load the environment to get all the assignments
    environment_id = get_environment_id(honeycomb_client, environment_name)
    add_classroom(output_path, environment_name, environment_id)

    # prep this output's environment index.json manifest file
    # this index will point to each camera's HLS and thumbnail assets
    manifest_path = os.path.join(output_path, environment_id, output_name, "index.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

    # track video json to write to environment's index.json
    video_meta = []

    # evaluate the assignments to filter out non-camera assignments
    assignments = get_assignments(honeycomb_client, environment_id)
    for idx, (assignment_id, assignment_name) in enumerate(assignments):
        datapoints = list(get_datapoint_keys_for_assignment_in_range(honeycomb_client, assignment_id, start, end))

        logging.info("%s has %i in %s=%s", assignment_name, len(datapoints), start, end)
        if len(datapoints) == 0:
            logging.warning("No videos for assignment: '{}':{}".format(assignment_id, assignment_name))

        # fetch all of the videos for each camera
        download_manifest = process_assignment_datapoints_for_download(f"{output_path}/{environment_id}/{output_name}/{assignment_name}/", datapoints, start, end)

        empty_clip_path = os.path.join(output_path, "empty_frames.video.mp4")

        execute_manifest(download_manifest, empty_clip_path, rewrite)
        if len(download_manifest["files"]) > 0:
            files_path = os.path.join(output_path, environment_id, output_name, assignment_name, "files.txt")
            video_out = os.path.join(output_path, environment_id, output_name, assignment_name, "output.mp4")
            hls_out = os.path.join(output_path, environment_id, output_name, assignment_name, "output.m3u8")
            hls_thumb_out = os.path.join(output_path, environment_id, output_name, assignment_name, "output-small.m3u8")
            thumb_path = os.path.join(output_path, environment_id, output_name, assignment_name, "output-small.mp4")
            preview_image_out = os.path.join(output_path, environment_id, output_name, assignment_name, "output-preview.jpg")
            preview_image_thumb_out = os.path.join(output_path, environment_id, output_name, assignment_name, "output-preview-small.jpg")
            with open(files_path, 'w') as fp:
                count = 0
                for line in sorted(download_manifest["files"]):
                    num_frames = count_frames(line)
                    if num_frames < 100:
                        pad_video(line, line, frames=(100 - num_frames))
                    elif num_frames > 100:
                        trim_video(line, line)

                    fp.write("file \'")
                    fp.write(os.path.basename(line))
                    # fp.write(f"_trimed.mp4\' duration 00:00:10.000 inpoint {vts(count)} outpoint {vts(count + 1)}\n")
                    fp.write(f"\' duration 00:00:10.000 inpoint {vts(count)} outpoint {vts(count + 1)}\n")
                    count += 1
                fp.flush()

            concat_videos(files_path, video_out, thumb_path=thumb_path, rewrite=rewrite)

            # prepare videos for HLS streaming
            prepare_hls(video_out, hls_out, rewrite=rewrite)
            prepare_hls(thumb_path, hls_thumb_out, rewrite=rewrite)

            generate_preview_image(hls_out, preview_image_out)
            generate_preview_image(hls_thumb_out, preview_image_thumb_out)

            video_meta.append({
                "device_id": assignment_id,
                "device_name": assignment_name,
                "url": f"/videos/{environment_id}/{output_name}/{assignment_name}/output.m3u8",
                "preview_url": f"/videos/{environment_id}/{output_name}/{assignment_name}/output-preview.jpg",
                "preview_thumbnail_url": f"/videos/{environment_id}/{output_name}/{assignment_name}/output-preview-small.jpg",
            })

        # Add a record in the classroom's index that points to this run's video feeds
        add_date_to_classroom(output_path, environment_id, start[:10], output_name, [start[11:], end[11:]])

        with open(manifest_path, 'w') as fp:
            json.dump({
                          "start": start,
                          "end": end,
                          "videos": video_meta,
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
