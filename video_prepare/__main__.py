import itertools
import pytz

import click
from dotenv import load_dotenv

load_dotenv()


from . import core
from .honeycomb_service import HoneycombClient
from .introspection import fetch_video_metadata_in_range
from .log import logger


cli_valid_date_formats = list(
    itertools.chain.from_iterable(
        map(
            lambda d: [f"{d}", f"{d}%z", f"{d} %z", f"{d} %Z"],
            ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        )
    )
)


def cli_timezone_aware(ctx, param, value):
    if value.tzinfo is None:
        return value.replace(tzinfo=pytz.UTC)

    return value.astimezone(pytz.utc)


@click.group()
def main():
    pass


@main.command()
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
def list_videos_for_environment_for_time_range(environment_name, output_path, output_name, start, end, camera):
    # load the environment to get all the assignments
    honeycomb_client = HoneycombClient()

    environment_id = honeycomb_client.get_environment_by_name(environment_name).get("environment_id")
    with open(f"{output_path}/{output_name}", "w", encoding="utf-8") as output_fp:
        output_fp.write("assignment_id,device_id,assigned_name,timestamp,data_id\n")
        # evaluate the assignments to filter out non-camera assignments
        assignments = honeycomb_client.get_assignments(environment_id)
        for assignment_id, device_id, assigned_name in assignments:
            if len(camera) > 0:
                if assignment_id not in camera and assigned_name not in camera:
                    logger.info(f"Skipping camera '{assignment_id}:{assigned_name}', not in supplied cameras param")
                    continue

            video_metadata = list(
                fetch_video_metadata_in_range(environment_id=environment_id, device_id=device_id, start=start, end=end)
            )
            for item in video_metadata:
                output_fp.write(
                    f"{assignment_id},{device_id},{assigned_name},{item['video_timestamp']},{item['data_id']}\n"
                )
        output_fp.flush()


@main.command(name="prepare-videos-for-environment-for-time-range")
@click.option(
    "--environment_name",
    "-e",
    help="name of the environment in honeycomb, required for using the honeycomb consumer",
    required=True,
)
@click.option("--video_directory", "-v", help="Directory to store prepared videos in", required=True)
@click.option(
    "--raw_video_storage_directory",
    help="Root directory where raw videos are stored. In production, this is the shared EFS volume's mount point. Providing this path will allow the video_streamer to copy files rather than fetch video files over http.",
)
@click.option(
    "--video_name",
    "-n",
    help="name given to subfolder where video is stored (i.e. /<<video_directory/<<environment_id>>/<<VIDEO_NAME>>/",
    required=True,
)
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
    help="DISABLED - append images/video to HLS feed (start time for given day must align)",
    is_flag=True,
    default=False,
)
@click.option(
    "--cleanup",
    help="Will remove downloaded/copied videos after generating streamable video. Use to cut down on storage costs. Note, videos will need to be fully reprocessed if streamable video needs to be regenerated",
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
def prepare_videos_for_environment_for_time_range(
    environment_name,
    video_directory,
    raw_video_storage_directory,
    video_name,
    start,
    end,
    rewrite,
    append,
    cleanup,
    camera,
):
    core.prepare_videos_for_environment_for_time_range(
        environment_name=environment_name,
        video_directory=video_directory,
        video_name=video_name,
        start=start,
        end=end,
        rewrite=rewrite,
        append=append,
        camera=camera,
        raw_video_storage_directory=raw_video_storage_directory,
        remove_video_files_after_processing=cleanup,
    )


if __name__ == "__main__":
    main(auto_envvar_prefix="HONEYCOMB")
