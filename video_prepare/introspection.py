from datetime import datetime

import video_io

from . import util


def fetch_video_metadata_in_range(environment_id, device_id, start, end):
    start_datetime = start
    if not isinstance(start, datetime):
        start_datetime = util.str_to_date(start)
    end_datetime = end
    if isinstance(end, datetime):
        end_datetime = util.str_to_date(end)

    videos = video_io.fetch_video_metadata(
        start=start_datetime,
        end=end_datetime,
        environment_id=environment_id,
        camera_device_ids=[device_id],
    )

    # for video in videos:
    #     file_extension = os.path.splitext(video['path'])[1]
    #     video_timestamp = video['video_timestamp'].strftime('%Y-%m-%dT%H:%M:%SZ')
    #     new_path = os.path.join(output_path, f"{video_timestamp}_{video['data_id']}{file_extension}")
    #
    #     #shutil.move(video['video_local_path'], new_path)
    #     video['video_streamer_path'] = new_path

    return videos
