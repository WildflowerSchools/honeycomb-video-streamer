from datetime import datetime, timedelta
import os
import os.path
import pytz
import shutil
import tempfile

import pandas as pd
import video_io

from .manifest import Manifest
from . import util


def get_environment_id(honeycomb_client, environment_name):
    environments = honeycomb_client.query.findEnvironment(
        name=environment_name)
    return environments.data[0].get('environment_id')


def get_assignments(honeycomb_client, environment_id):
    assignments = honeycomb_client.query.query(
        """
        query getEnvironment ($environment_id: ID!) {
          getEnvironment(environment_id: $environment_id) {
            environment_id
            name
            assignments(current: true) {
              assignment_id
              assigned_type
              assigned {
                ... on Device {
                  device_id
                  device_type
                  part_number
                  name
                  tag_id
                  description
                  serial_number
                  mac_address
                }
              }
            }
          }
        }
        """,
        {"environment_id": environment_id}).get("getEnvironment").get("assignments")
    return [(assignment["assignment_id"], assignment["assigned"]["device_id"], assignment["assigned"]["name"]) for assignment in assignments if assignment["assigned_type"]
            == "DEVICE" and assignment["assigned"]["device_type"] in ["PI3WITHCAMERA", "PI4WITHCAMERA"]]


def fetch_video_metadata_in_range(
        environment_id, device_id, start, end):
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
    return ts.to_pydatetime().astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def process_video_metadata_for_download(
        video_metadata, start, end, manifest=Manifest()):
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

    datetimeindex = pd.date_range(
        start_datetime,
        end_datetime -
        timedelta(
            seconds=10),
        freq="10S",
        tz=pytz.UTC)

    # Convert datapoints to a dataframe to use pd timeseries functionality
    df_datapoints = pd.DataFrame(video_metadata)
    if len(video_metadata) > 0:
        # Move timestamp column to datetime index
        df_datapoints['video_timestamp'] = pd.to_datetime(
            df_datapoints['video_timestamp'], utc=True)
        df_datapoints = df_datapoints.set_index(
            pd.DatetimeIndex(df_datapoints['video_timestamp']))
        df_datapoints = df_datapoints.drop(columns=['video_timestamp'])
        # Scrub duplicates (these shouldn't exist)
        df_datapoints = df_datapoints[~df_datapoints.index.duplicated(
            keep='first')]
        # Fill in missing time indices
        df_datapoints = df_datapoints.reindex(datetimeindex)

    for idx_datetime, row in df_datapoints.iterrows():
        start_formatted_time = clean_pd_ts(idx_datetime)
        end_formatted_time = clean_pd_ts(idx_datetime + timedelta(seconds=10))
        # output = os.path.join(target, f"{start_formatted_time}.video.mp4")

        if pd.isnull(row['data_id']):
            manifest.add_to_missing(start=start_formatted_time,
                                    end=end_formatted_time)
        else:
            manifest.add_to_download(video_metadatum=row.to_dict(),
                                     start=start_formatted_time,
                                     end=end_formatted_time)

    return manifest
