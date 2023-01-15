from datetime import datetime, timedelta

import pandas as pd
import pytz
import video_io

from .manifest import Manifest
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


def clean_pd_ts(ts):
    return ts.to_pydatetime().astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def process_video_metadata_for_download(video_metadata, start, end, manifest=Manifest()):
    """
    Query and fetch video clips from the datapoints endpoint. Missing clips will be added
    to the output dict's "missing" field

    :param target:
    :param datapoints:
    :param start:
    :param end:
    :param manifest:
    :return: Manifest
    """
    if isinstance(end, str):
        end_datetime = util.str_to_date(end)
    else:
        end_datetime = end

    if isinstance(start, str):
        start_datetime = util.str_to_date(start)
    else:
        start_datetime = start

    datetimeindex = pd.date_range(start_datetime, end_datetime - timedelta(seconds=10), freq="10S", tz=pytz.UTC)

    # Convert datapoints to a dataframe to use pd timeseries functionality
    df_datapoints = pd.DataFrame(video_metadata)
    if len(video_metadata) > 0:
        # Move timestamp column to datetime index
        df_datapoints["video_timestamp"] = pd.to_datetime(df_datapoints["video_timestamp"], utc=True)
        df_datapoints = df_datapoints.set_index(pd.DatetimeIndex(df_datapoints["video_timestamp"]))
        df_datapoints = df_datapoints.drop(columns=["video_timestamp"])
        # Scrub duplicates (these shouldn't exist)
        df_datapoints = df_datapoints[~df_datapoints.index.duplicated(keep="first")]

    # Fill in missing time indices
    df_datapoints = df_datapoints.reindex(datetimeindex)
    # TODO: Consider handling empty df_datapoints and lining it up with timestamps that cover a given start and end time
    for idx_datetime, row in df_datapoints.iterrows():
        start_formatted_time = clean_pd_ts(idx_datetime)
        end_formatted_time = clean_pd_ts(idx_datetime + timedelta(seconds=10))
        # output = os.path.join(target, f"{start_formatted_time}.video.mp4")

        if "data_id" not in row or pd.isnull(row["data_id"]) or "path" not in row or pd.isnull(row["path"]):
            manifest.add_to_missing(start=start_formatted_time, end=end_formatted_time)
        else:
            manifest.add_to_download(video_metadatum=row.to_dict(), start=start_formatted_time, end=end_formatted_time)

    return manifest
