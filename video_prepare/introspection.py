import time
from datetime import datetime

import requests
import video_io

from .log import logger
from . import util


def fetch_video_metadata_in_range(environment_id, device_id, start, end):
    start_datetime = start
    if not isinstance(start, datetime):
        start_datetime = util.str_to_date(start)
    end_datetime = end
    if isinstance(end, datetime):
        end_datetime = util.str_to_date(end)

    def _fetch(retry=0):
        try:
            return video_io.fetch_video_metadata(
                start=start_datetime,
                end=end_datetime,
                environment_id=environment_id,
                camera_device_ids=[device_id],
            )
        except requests.exceptions.HTTPError as e:
            logger.warning(f"video_io.fetch_video_metadata failed w/ {e.response.status_code} code: {e}")
            if retry >= 3:
                raise e

            time.sleep(0.5)
            return _fetch(retry + 1)

    videos = _fetch()
    return videos
