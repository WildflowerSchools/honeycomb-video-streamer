from datetime import timedelta
import itertools
import json
import logging
import os
import os.path
import pytz

import click
from dotenv import load_dotenv
import honeycomb

from .introspection import (
    get_assignments,
    fetch_video_metadata_in_range,
    process_video_metadata_for_download,
    get_environment_id,
)
from .transcode import (
    concat_videos,
    count_frames,
    get_duration,
    generate_preview_image,
    pad_video,
    prepare_hls,
    trim_video,
    copy_technical_difficulties_clip,
)
from .manifest import Manifest
from .manifestations import add_classroom, add_date_to_classroom
from . import const, util


load_dotenv()


HONEYCOMB_URI = os.getenv("HONEYCOMB_URI", "https://honeycomb.api.wildflower-tech.org/graphql")
HONEYCOMB_TOKEN_URI = os.getenv("HONEYCOMB_TOKEN_URI", "https://wildflowerschools.auth0.com/oauth/token")
HONEYCOMB_AUDIENCE = os.getenv("HONEYCOMB_AUDIENCE", "https://honeycomb.api.wildflowerschools.org")
HONEYCOMB_CLIENT_ID = os.getenv("HONEYCOMB_CLIENT_ID")
HONEYCOMB_CLIENT_SECRET = os.getenv("HONEYCOMB_CLIENT_SECRET")

cli_valid_date_formats = list(
    itertools.chain.from_iterable(
        map(
            lambda d: ["{}".format(d), "{}%z".format(d), "{} %z".format(d), "{} %Z".format(d)],
            ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        )
    )
)


def cli_timezone_aware(ctx, param, value):
    if value.tzinfo is None:
        return value.replace(tzinfo=pytz.UTC)
    else:
        return value.astimezone(pytz.utc)


@click.group()
@click.pass_context
def main(ctx):
    ctx.ensure_object(dict)
    if HONEYCOMB_CLIENT_ID is None:
        raise ValueError("HONEYCOMB_CLIENT_ID is required")
    if HONEYCOMB_CLIENT_SECRET is None:
        raise ValueError("HONEYCOMB_CLIENT_SECRET is required")
    ctx.obj["honeycomb_client"] = honeycomb.HoneycombClient(
        uri=HONEYCOMB_URI,
        client_credentials={
            "token_uri": HONEYCOMB_TOKEN_URI,
            "audience": HONEYCOMB_AUDIENCE,
            "client_id": HONEYCOMB_CLIENT_ID,
            "client_secret": HONEYCOMB_CLIENT_SECRET,
        },
    )


@main.command()
@click.pass_context
@click.option(
    "--environment_name",
    "-e",
    help="name of the environment in honeycomb, required for using the honeycomb consumer",
    required=True,
)
@click.option("--output_path", "-o", help="path to output prepared videos to", required=True)
@click.option("--output_name", "-n", help="name to give the output video", required=True)
@click.option("--day", "-d", help="day of video to load expects format to be YYYY-MM-DD", required=True)
def prepare_videos_for_environment_for_day(ctx, environment_name, output_path, output_name, day):
    datetime_of_day = util.date_to_day_format(day)
    start = (datetime_of_day + timedelta(hours=13)).isoformat()
    end = (datetime_of_day + timedelta(hours=22)).isoformat()
    prepare_videos_for_environment_for_time_range(ctx, environment_name, output_path, output_name, start, end)


@main.command()
@click.pass_context
@click.option(
    "--environment_name",
    "-e",
    help="name of the environment in honeycomb, required for using the honeycomb consumer",
    required=True,
)
@click.option("--output_path", "-o", help="path to output prepared videos to", required=True)
@click.option("--output_name", "-n", help="name to give the output video", required=True)
@click.option(
    "--start",
    type=click.DateTime(formats=cli_valid_date_formats),
    required=True,
    callback=cli_timezone_aware,
    help="start time of video to load expects format to be YYYY-MM-DDTHH:MM Z",
)
@click.option(
    "--end",
    type=click.DateTime(formats=cli_valid_date_formats),
    required=True,
    callback=cli_timezone_aware,
    help="end time of video to load expects format to be YYYY-MM-DDTHH:MM Z",
)
@click.option(
    "--camera",
    "-c",
    help="list of cameras to generate video for (ids/names)",
    required=False,
    multiple=True,
    default=[],
)
def list_videos_for_environment_for_time_range(ctx, environment_name, output_path, output_name, start, end, camera):
    honeycomb_client = ctx.obj["honeycomb_client"]
    # load the environment to get all the assignments
    environment_id = get_environment_id(honeycomb_client, environment_name)
    with open(f"{output_path}/{output_name}", "w") as output_fp:
        output_fp.write(f"assignment_id,device_id,assigned_name,timestamp,data_id\n")
        # evaluate the assignments to filter out non-camera assignments
        assignments = get_assignments(honeycomb_client, environment_id)
        for assignment_id, device_id, assigned_name in assignments:
            if len(camera) > 0:
                if assignment_id not in camera and assigned_name not in camera:
                    logging.info(
                        "Skipping camera '{}:{}', not in supplied cameras param".format(assignment_id, assigned_name)
                    )
                    continue

            video_metadata = list(
                fetch_video_metadata_in_range(environment_id=environment_id, device_id=device_id, start=start, end=end)
            )
            for item in video_metadata:
                output_fp.write(
                    f"{assignment_id},{device_id},{assigned_name},{item['video_timestamp']},{item['data_id']}\n"
                )
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
@click.option(
    "--environment_name",
    "-e",
    help="name of the environment in honeycomb, required for using the honeycomb consumer",
    required=True,
)
@click.option("--output_path", "-o", help="path to output prepared videos to", required=True)
@click.option("--output_name", "-n", help="name to give the output video", required=True)
@click.option(
    "--start",
    type=click.DateTime(formats=cli_valid_date_formats),
    required=True,
    callback=cli_timezone_aware,
    help="start time of video to load expects format to be YYYY-MM-DDTHH:MM Z",
)
@click.option(
    "--end",
    type=click.DateTime(formats=cli_valid_date_formats),
    required=True,
    callback=cli_timezone_aware,
    help="end time of video to load expects format to be YYYY-MM-DDTHH:MM Z",
)
@click.option(
    "--rewrite",
    help="rewrite any generated images/video (i.e. hls feeds) (already downloaded raw videos are not destroyed or re-downloaded)",
    is_flag=True,
    default=False,
)
@click.option(
    "--append",
    help="append images/video to HLS feed (start time for given day must align)",
    is_flag=True,
    default=False,
)
@click.option(
    "--camera",
    "-c",
    help="list of cameras to generate video for (ids/names)",
    required=False,
    multiple=True,
    default=[],
)
@click.option("--hls/--no-hls", "generate_hls", help="turn on/off hls generation", required=False, default=True)
def prepare_videos_for_environment_for_time_range(
    ctx, environment_name, output_path, output_name, start, end, rewrite, append, camera, generate_hls
):
    if rewrite:
        logging.warning("Rewrite flag enabled! All generated images/video will be recreated.")
    elif append:
        logging.warning("If existing video is discovered, new video will be appended")

    honeycomb_client = ctx.obj["honeycomb_client"]
    # load the environment to get all the assignments
    environment_id = get_environment_id(honeycomb_client, environment_name)
    add_classroom(output_path, environment_name, environment_id)

    # prep this output's environment index.json manifest file
    # this index will point to each camera's HLS and thumbnail assets
    env_specific_output_dir = os.path.join(output_path, environment_id, output_name)
    manifest_path = os.path.join(env_specific_output_dir, "index.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

    empty_clip_path = const.empty_clip_path(env_specific_output_dir)
    copy_technical_difficulties_clip(clip_path=empty_clip_path, output_path=empty_clip_path, rewrite=rewrite)

    index_manifest = {}
    if not os.path.isfile(manifest_path):
        if rewrite is False:
            logging.warning(f"Manifest '{manifest_path}' missing. Setting rewrite flag to True.")
        rewrite = True
    else:
        with open(manifest_path, "r") as fp:
            try:
                index_manifest = json.load(fp)
            except ValueError as e:
                logging.error("Failed loading {} - {}".format(index_manifest, e))
                rewrite = True

    # track video json to write to environment's index.json
    all_video_meta = index_manifest.get("videos", [])

    # evaluate the assignments to filter out non-camera assignments
    assignments = get_assignments(honeycomb_client, environment_id)
    for idx_ii, (assignment_id, device_id, assigned_name) in enumerate(assignments):
        if len(camera) > 0:
            if assignment_id not in camera and device_id not in camera and assigned_name not in camera:
                logging.info("Skipping camera '{}:{}', not in supplied cameras param".format(device_id, assigned_name))
                continue

        camera_specific_directory = os.path.join(output_path, environment_id, output_name, assigned_name)
        os.makedirs(camera_specific_directory, exist_ok=True)

        rewrite_current = rewrite
        logging.info(
            "Fetching video metadata for camera '{}:{}' - {} (start) - {} (end)".format(
                device_id, assigned_name, start, end
            )
        )
        video_metadata = list(
            fetch_video_metadata_in_range(environment_id=environment_id, device_id=device_id, start=start, end=end)
        )

        logging.info("%s has %i videos between %s to %s", assigned_name, len(video_metadata), start, end)
        if len(video_metadata) == 0:
            logging.warning("No videos for assignment: '{}':{}".format(assignment_id, assigned_name))

        # fetch all of the videos for each camera, records are returned ordered by timestamp
        # missing clips are stored behind the "missing" attribute
        # target=f"{output_path}/{environment_id}/{output_name}/{assigned_name}/",
        manifest = process_video_metadata_for_download(
            video_metadata=video_metadata,
            start=start,
            end=end,
            manifest=Manifest(output_directory=camera_specific_directory, empty_clip_path=empty_clip_path),
        )
        if len(manifest.get_files()) == 0:
            continue

        manifest.execute()

        hls_out = os.path.join(camera_specific_directory, "output.m3u8")
        hls_thumb_out = os.path.join(camera_specific_directory, "output-small.m3u8")
        preview_image_out = os.path.join(camera_specific_directory, "output-preview.jpg")
        preview_image_thumb_out = os.path.join(camera_specific_directory, "output-preview-small.jpg")
        camera_video_history_path = os.path.join(camera_specific_directory, "history.json")

        last_end_time = start
        camera_video_history = []
        if index_manifest is None or index_manifest == {} or not os.path.isfile(camera_video_history_path):
            rewrite_current = True
        else:
            with open(camera_video_history_path, "r") as fp:
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
                camera_start_time = camera_video_history[0]["start_time"]
                camera_end_time = camera_video_history[-1]["end_time"]
                if util.str_to_date(index_manifest["start"]) != util.str_to_date(camera_start_time):
                    logger.error(
                        "Unexpected start_time for camera '{}': {} != {}. Recreating HLS stream...".format(
                            assigned_name, camera_start_time, index_manifest["start"]
                        )
                    )
                    camera_video_history = []
                    rewrite_current = True
                else:
                    expected_duration = (
                        util.str_to_date(camera_end_time) - util.str_to_date(camera_start_time)
                    ).total_seconds()
                    actual_duration = get_duration(hls_out)
                    if actual_duration != expected_duration:
                        logger.error(
                            "Unexpected duration for camera '{}': {} != {}. Recreating HLS stream...".format(
                                assigned_name, expected_duration, actual_duration
                            )
                        )
                        camera_video_history = []
                        rewrite_current = True

                for record in camera_video_history:
                    if last_end_time is None:
                        last_end_time = util.date_to_video_history_format(record["end_time"])
                    else:
                        if util.str_to_date(record["end_time"]) > util.str_to_date(last_end_time):
                            last_end_time = util.date_to_video_history_format(record["end_time"])

        current_input_files_path = os.path.join(camera_specific_directory, f"files_{len(camera_video_history)}.txt")
        video_out_path = os.path.join(camera_specific_directory, f"output_{len(camera_video_history)}.mp4")
        thumb_out_path = os.path.join(camera_specific_directory, f"output-small_{len(camera_video_history)}.mp4")

        current_video_history = {
            "start_time": last_end_time,
            "end_time": None,
            "files": [],
            "video_out_path": video_out_path,
            "thumb_out_path": thumb_out_path,
        }

        already_processed_files = list(map(lambda x: x["files"], camera_video_history))
        already_processed_files = list(itertools.chain(*already_processed_files))

        with open(current_input_files_path, "w") as fp:
            count = 0
            for file in sorted(manifest.get_files(), key=lambda x: x["video_streamer_path"]):
                video_snippet_path = file["video_streamer_path"]
                # Skip video files that have already been processed
                if video_snippet_path in already_processed_files:
                    continue

                # Process new video files
                current_video_history["files"].append(video_snippet_path)

                if current_video_history["end_time"] is None or file["end"] > util.str_to_date(
                    current_video_history["end_time"]
                ):
                    current_video_history["end_time"] = util.date_to_video_history_format(file["end"])

                logger.info(f"Preparing '{video_snippet_path}' for HLS generation...")
                num_frames = count_frames(video_snippet_path)
                if num_frames < 100:  # and num_frames > 97:
                    pad_video(video_snippet_path, video_snippet_path, frames=(100 - num_frames))
                if num_frames == 101:
                    trim_video(video_snippet_path, video_snippet_path)

                fp.write(f"file 'file:{video_snippet_path}")
                fp.write(
                    f"' duration 00:00:{util.format_frames(num_frames)} inpoint {vts(count)} outpoint {vts(count + num_frames)}\n"
                )
                count += num_frames
            fp.flush()

        if len(current_video_history["files"]) > 0:
            concat_videos(current_input_files_path, video_out_path, thumb_path=thumb_out_path, rewrite=True)

            if not generate_hls:
                logger.info("Generated: {}".format(video_out_path))
                logger.info("Skipping HLS generation")
                continue

            # prepare videos for HLS streaming
            prepare_hls(video_out_path, hls_out, rewrite=rewrite_current, append=append)
            prepare_hls(thumb_out_path, hls_thumb_out, rewrite=rewrite_current, append=append)

            camera_video_history.append(current_video_history)

            generate_preview_image(hls_out, preview_image_out)
            generate_preview_image(hls_thumb_out, preview_image_thumb_out)

        if generate_hls:
            current_video_meta = {
                "device_id": device_id,
                "device_name": assigned_name,
                "url": f"/videos/{environment_id}/{output_name}/{assigned_name}/output.m3u8",
                "preview_url": f"/videos/{environment_id}/{output_name}/{assigned_name}/output-preview.jpg",
                "preview_thumbnail_url": f"/videos/{environment_id}/{output_name}/{assigned_name}/output-preview-small.jpg",
            }

            ######
            # Update or append to the video_meta data object
            ######
            updated_existing_video_meta_record = False
            for idx_jj, meta_record in enumerate(all_video_meta):
                if meta_record["device_id"] == device_id:
                    updated_existing_video_meta_record = True
                    all_video_meta[idx_jj] = current_video_meta
                    break

            if not updated_existing_video_meta_record:
                all_video_meta.append(current_video_meta)
            ######

            with open(camera_video_history_path, "w") as fp:
                json.dump(camera_video_history, fp, cls=util.DateTimeEncoder)
                fp.flush()

            # Add a record in the classroom's index that points to this run's video
            # feeds
            add_date_to_classroom(
                root_path=output_path,
                classroom_id=environment_id,
                date=start.strftime("%Y-%m-%d"),
                name=output_name,
                time_range=[start.strftime("%H:%M:%S%z"), end.strftime("%H:%M:%S%z")],
            )

            with open(manifest_path, "w") as fp:
                json.dump(
                    {"start": start, "end": end, "videos": all_video_meta, "building": (idx_ii < len(assignments) - 1)},
                    fp,
                    cls=util.DateTimeEncoder,
                )
                fp.flush()
                # done


if __name__ == "__main__":
    logger = logging.getLogger()

    logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    main(auto_envvar_prefix="HONEYCOMB")
