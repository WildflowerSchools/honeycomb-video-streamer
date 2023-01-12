import datetime
import os
from typing import List

from . import const, util
from .honeycomb_service import HoneycombClient
from .introspection import fetch_video_metadata_in_range, process_video_metadata_for_download
from .log import logger
from .stream_service import client as stream_service_client, models
from .transcode import (
    concat_videos,
    count_frames,
    generate_preview_image,
    pad_video,
    prepare_hls,
    trim_video,
    copy_technical_difficulties_clip,
)
from .manifest import Manifest


def prepare_videos_for_environment_for_time_range(
    environment_name: str,
    video_directory: str,
    video_name: str,
    start: datetime.datetime,
    end: datetime.datetime,
    rewrite: bool = False,
    append: bool = False,
    camera: List[str] = [],
):
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

    streaming_client = stream_service_client.StreamServiceClient()
    playset = streaming_client.get_playset_by_name(environment_id=environment_id, playset_name=video_name)

    if playset is not None:
        if rewrite is False:
            logger.warning(
                f"Rewrite flag set to False and streamable video for environment '{environment_name}' with name '{video_name}' already exists"
            )
            return
        else:
            streaming_client.delete_playset_by_name_if_exists(environment_id=environment_id, playset_name=video_name)

    playset = streaming_client.create_playset(
        playset=models.Playset(classroom_id=environment_id, name=video_name, start_time=start, end_time=end)
    )

    # manifest_path = os.path.join(output_dir, "index.json")
    os.makedirs(os.path.dirname(output_dir), exist_ok=True)

    empty_clip_path = const.empty_clip_path(output_dir)
    copy_technical_difficulties_clip(clip_path=empty_clip_path, output_path=empty_clip_path, rewrite=rewrite)

    index_manifest = {}
    # if not os.path.isfile(manifest_path):
    #     if rewrite is False:
    #         logger.warning(f"Manifest '{manifest_path}' missing. Setting rewrite flag to True.")
    #     rewrite = True
    # else:
    #     with open(manifest_path, "r") as fp:
    #         try:
    #             index_manifest = json.load(fp)
    #         except ValueError as e:
    #             logger.error("Failed loading {} - {}".format(index_manifest, e))
    #             rewrite = True

    # track video json to write to environment's index.json
    all_video_meta: List[models.VideoResponse] = index_manifest.get("videos", [])

    # evaluate the assignments to filter out non-camera assignments
    assignments = honeycomb_client.get_assignments(environment_id)
    for idx_ii, (assignment_id, device_id, assigned_name) in enumerate(assignments):
        if len(camera) > 0:
            if assignment_id not in camera and device_id not in camera and assigned_name not in camera:
                logger.info("Skipping camera '{}:{}', not in supplied cameras param".format(device_id, assigned_name))
                continue

        camera_specific_directory = os.path.join(output_dir, assigned_name)
        os.makedirs(camera_specific_directory, exist_ok=True)

        rewrite_current = rewrite
        logger.info(
            "Fetching video metadata for camera '{}:{}' - {} (start) - {} (end)".format(
                device_id, assigned_name, start, end
            )
        )
        video_metadata = list(
            fetch_video_metadata_in_range(environment_id=environment_id, device_id=device_id, start=start, end=end)
        )

        logger.info("%s has %i videos between %s to %s", assigned_name, len(video_metadata), start, end)
        if len(video_metadata) == 0:
            logger.warning("No videos for assignment: '{}':{}".format(assignment_id, assigned_name))

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
        # camera_video_history_path = os.path.join(camera_specific_directory, "history.json")

        # last_end_time = start
        # camera_video_history = []
        # if index_manifest is None or index_manifest == {} or not os.path.isfile(camera_video_history_path):
        #     rewrite_current = True
        # else:
        #     with open(camera_video_history_path, "r") as fp:
        #         try:
        #             camera_video_history = json.load(fp)
        #         except ValueError as e:
        #             logger.error("Failed loading {} - {}".format(camera_video_history_path, e))
        #             rewrite_current = True
        #
        #     is_valid_history = camera_video_history is not None and isinstance(camera_video_history, list)
        #     is_valid_and_has_history = is_valid_history and len(camera_video_history) > 0
        #
        #     if not is_valid_history:
        #         camera_video_history = []
        #         rewrite_current = True
        #
        #     elif is_valid_and_has_history:
        #         camera_start_time = camera_video_history[0]["start_time"]
        #         camera_end_time = camera_video_history[-1]["end_time"]
        #         if util.str_to_date(index_manifest["start"]) != util.str_to_date(camera_start_time):
        #             logger.error(
        #                 "Unexpected start_time for camera '{}': {} != {}. Recreating HLS stream...".format(
        #                     assigned_name, camera_start_time, index_manifest["start"]
        #                 )
        #             )
        #             camera_video_history = []
        #             rewrite_current = True
        #         else:
        #             expected_duration = (
        #                     util.str_to_date(camera_end_time) - util.str_to_date(camera_start_time)
        #             ).total_seconds()
        #             actual_duration = get_duration(hls_out)
        #             if actual_duration != expected_duration:
        #                 logger.error(
        #                     "Unexpected duration for camera '{}': {} != {}. Recreating HLS stream...".format(
        #                         assigned_name, expected_duration, actual_duration
        #                     )
        #                 )
        #                 camera_video_history = []
        #                 rewrite_current = True
        #
        #         for record in camera_video_history:
        #             if last_end_time is None:
        #                 last_end_time = util.date_to_video_history_format(record["end_time"])
        #             else:
        #                 if util.str_to_date(record["end_time"]) > util.str_to_date(last_end_time):
        #                     last_end_time = util.date_to_video_history_format(record["end_time"])

        current_input_files_path = os.path.join(camera_specific_directory, f"m3u8_files.txt")
        video_out_path = os.path.join(camera_specific_directory, f"output.mp4")
        thumb_out_path = os.path.join(camera_specific_directory, f"output-small.mp4")

        current_video_history = {
            "start_time": start,
            "end_time": None,
            "files": [],
            "video_out_path": video_out_path,
            "thumb_out_path": thumb_out_path,
        }

        # already_processed_files = list(map(lambda x: x["files"], camera_video_history))
        # already_processed_files = list(itertools.chain(*already_processed_files))

        with open(current_input_files_path, "w") as fp:
            count = 0
            for file in sorted(manifest.get_files(), key=lambda x: x["video_streamer_path"]):
                video_snippet_path = file["video_streamer_path"]
                # Skip video files that have already been processed
                # if video_snippet_path in already_processed_files and not rewrite:
                #     continue

                # Process new video files
                logger.info(f"Preparing '{video_snippet_path}' for HLS generation...")
                try:
                    num_frames = count_frames(video_snippet_path)
                except Exception as err:
                    logger.warning(f"Unable to probe '{video_snippet_path}', replacing with empty video clip")
                    video_snippet_path = empty_clip_path
                    count_frames(video_snippet_path)

                if num_frames < 100:
                    pad_video(video_snippet_path, video_snippet_path, frames=(100 - num_frames))
                if num_frames > 100:
                    trim_video(video_snippet_path, video_snippet_path)

                fp.write(
                    f"file 'file:{video_snippet_path}' duration 00:00:{util.format_frames(num_frames)} inpoint {util.vts(count)} outpoint {util.vts(count + num_frames)}\n"
                )

                current_video_history["files"].append(video_snippet_path)
                if current_video_history["end_time"] is None or file["end"] > util.str_to_date(
                    current_video_history["end_time"]
                ):
                    current_video_history["end_time"] = util.date_to_video_history_format(file["end"])

                count += num_frames
            fp.flush()

        if len(current_video_history["files"]) > 0:
            concat_videos(
                input_path=current_input_files_path, output_path=video_out_path, thumb_path=thumb_out_path, rewrite=True
            )
            logger.info("Generated: {}".format(video_out_path))

        if len(current_video_history["files"]) > 0:
            # prepare videos for HLS streaming
            prepare_hls(video_out_path, hls_out, rewrite=rewrite_current, append=append)
            prepare_hls(thumb_out_path, hls_thumb_out, rewrite=rewrite_current, append=append)

            # camera_video_history.append(current_video_history)

            generate_preview_image(hls_out, preview_image_out)
            generate_preview_image(hls_thumb_out, preview_image_thumb_out)

        current_video = models.Video(
            playset_id=playset.id,
            device_id=device_id,
            device_name=assigned_name,
            url=f"/videos/{environment_id}/{video_name}/{assigned_name}/output.m3u8",
            preview_url=f"/videos/{environment_id}/{video_name}/{assigned_name}/output-preview.jpg",
            preview_thumbnail_url=f"/videos/{environment_id}/{video_name}/{assigned_name}/output-preview-small.jpg",
        )

        ######
        # Update or append to the video_meta data object
        ######
        updated_existing_video_meta_record = False
        for idx_jj, video_record in enumerate(all_video_meta):
            if video_record.device_id == device_id:
                updated_existing_video_meta_record = True
                all_video_meta[idx_jj] = current_video
                break

        if not updated_existing_video_meta_record:
            all_video_meta.append(current_video)
        ######

        # with open(camera_video_history_path, "w") as fp:
        #     json.dump(camera_video_history, fp, cls=util.DateTimeEncoder)
        #     fp.flush()

        # Add a record in the classroom's index that points to this run's video
        # feeds
        streaming_client.add_video_to_playset(video=current_video)
        # add_date_to_classroom(
        #     root_path=output_path,
        #     classroom_id=environment_id,
        #     date=start.strftime("%Y-%m-%d"),
        #     name=output_name,
        #     time_range=[start.strftime("%H:%M:%S%z"), end.strftime("%H:%M:%S%z")],
        # )

        # with open(manifest_path, "w") as fp:
        #     json.dump(
        #         {"start": start, "end": end, "videos": all_video_meta, "building": (idx_ii < len(assignments) - 1)},
        #         fp,
        #         cls=util.DateTimeEncoder,
        #     )
        #     fp.flush()
        # done
