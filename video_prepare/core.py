import datetime
import os
from typing import List, Optional

from . import const
from .honeycomb_service import HoneycombClient
from .introspection import fetch_video_metadata_in_range
from .log import logger
from .stream_service import client as stream_service_client, models
from .transcode import (
    copy_technical_difficulties_clip,
)
from .streaming_generator import StreamingGenerator


def prepare_videos_for_environment_for_time_range(
    environment_name: str,
    video_directory: str,
    video_name: str,
    start: datetime.datetime,
    end: datetime.datetime,
    rewrite: bool = False,
    append: bool = False,
    camera: Optional[List[str]] = None,
    raw_video_storage_directory: Optional[str] = None,
    remove_video_files_after_processing: bool = False,
):
    if camera is None:
        camera = []

    if rewrite:
        logger.warning("Rewrite flag enabled! All generated images/video will be recreated.")
    elif append:
        # logger.warning("If existing video is discovered, new video will be appended")
        logger.warning("After switching to DB storage, append mode has been disabled")
        append = False

    honeycomb_client = HoneycombClient()

    # load the environment to get all the assignments
    environment_id = honeycomb_client.get_environment_by_name(environment_name).get("environment_id")
    # add_classroom(video_directory, environment_name, environment_id)

    # prep this output's environment index.json manifest file
    # this index will point to each camera's HLS and thumbnail assets
    output_dir = os.path.join(video_directory, environment_id, video_name)
    os.makedirs(output_dir, exist_ok=True)

    streaming_client = stream_service_client.StreamServiceClient()
    playset = streaming_client.get_playset_by_name(environment_id=environment_id, playset_name=video_name)

    if playset is not None:
        if rewrite is False:
            logger.warning(
                f"Rewrite flag set to False and streamable video for environment '{environment_name}' with name '{video_name}' already exists"
            )
            return

        streaming_client.delete_playset_by_name_if_exists(environment_id=environment_id, playset_name=video_name)

    playset = streaming_client.create_playset(
        playset=models.Playset(classroom_id=environment_id, name=video_name, start_time=start, end_time=end)
    )

    empty_clip_path = const.empty_clip_path(output_dir)
    copy_technical_difficulties_clip(clip_path=empty_clip_path, output_path=empty_clip_path, rewrite=rewrite)

    assignments = honeycomb_client.get_assignments(environment_id)
    for _, (assignment_id, device_id, assigned_name) in enumerate(assignments):
        if len(camera) > 0:
            if assignment_id not in camera and device_id not in camera and assigned_name not in camera:
                logger.info(f"Skipping camera '{device_id}:{assigned_name}', not in supplied cameras param")
                continue

        camera_specific_directory = os.path.join(output_dir, assigned_name)
        os.makedirs(camera_specific_directory, exist_ok=True)

        logger.info(f"Fetching video metadata for camera '{device_id}:{assigned_name}' - {start} (start) - {end} (end)")
        video_metadata = list(
            fetch_video_metadata_in_range(environment_id=environment_id, device_id=device_id, start=start, end=end)
        )

        logger.info(f"{assigned_name} has {len(video_metadata)} videos between {start} to {end}")
        if len(video_metadata) == 0:
            logger.warning(f"No videos for assignment: '{assignment_id}':{assigned_name}")

        streaming_generator = StreamingGenerator(
            video_metadata=video_metadata,
            start=start,
            end=end,
            output_directory=camera_specific_directory,
            empty_clip_path=empty_clip_path,
            raw_video_storage_directory=raw_video_storage_directory,
        ).load()

        if streaming_generator.file_count() == 0:
            logger.info(f"No videos found for {device_id}:{assigned_name}, no streamable video to be generated")
            continue

        try:
            streaming_generator.execute(rewrite=rewrite)
        except Exception as e:
            logger.error(f"Exception generating streamable video for {device_id}:{assigned_name}")
            logger.error(e)
            continue

        streaming_generator.cleanup(remove_processed_files=remove_video_files_after_processing)

        current_video = models.Video(
            playset_id=playset.id,
            device_id=device_id,
            device_name=assigned_name,
            url=f"/videos/{environment_id}/{video_name}/{assigned_name}/output.m3u8",
            preview_url=f"/videos/{environment_id}/{video_name}/{assigned_name}/output-preview.jpg",
            preview_thumbnail_url=f"/videos/{environment_id}/{video_name}/{assigned_name}/output-preview.jpg",
        )
        streaming_client.add_video_to_playset(video=current_video)
