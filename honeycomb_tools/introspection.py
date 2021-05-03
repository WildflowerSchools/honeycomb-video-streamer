from datetime import timedelta
import os
import os.path
import pytz

import pandas as pd

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
    return [(assignment["assignment_id"], assignment["assigned"]["name"]) for assignment in assignments if assignment["assigned_type"]
            == "DEVICE" and assignment["assigned"]["device_type"] in ["PI3WITHCAMERA", "PI4WITHCAMERA"]]


def get_datapoint_keys_for_assignment_in_range(
        honeycomb_client, assignment_id, start, end):
    query_pages = """
        query searchDatapoints($cursor: String, $assignment_id: String, $start: String, $end: String) {
          searchDatapoints(
            query: { operator: AND, children: [
                { operator: EQ, field: "source", value: $assignment_id },
                { operator: GTE, field: "timestamp", value: $start },
                { operator: LT, field: "timestamp", value: $end },
            ] }
            page: { cursor: $cursor, max: 1000, sort: {field: "timestamp", direction: DESC} }
          ) {
            page_info {
              count
              cursor
            }
            data {
              data_id
              timestamp
              format
              tags
              file {
                size
                key
                bucketName
                contentType
              }
            }
          }
        }
        """
    cursor = ""
    while True:
        page = honeycomb_client.raw_query(
            query_pages, {
                "assignment_id": assignment_id, "start": start, "end": end, "cursor": cursor})
        page_info = page.get("searchDatapoints").get("page_info")
        data = page.get("searchDatapoints").get("data")
        cursor = page_info.get("cursor")
        if page_info.get("count") == 0:
            break
        for item in data:
            yield item


def clean_pd_ts(ts):
    return ts.to_pydatetime().replace(tzinfo=None).isoformat(timespec='seconds') + 'Z'


def process_assignment_datapoints_for_download(
        target, datapoints, start, end, manifest=Manifest()):
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
    df_datapoints = pd.DataFrame(datapoints)
    if len(datapoints) > 0:
        # Move timestamp column to datetime index
        df_datapoints['timestamp'] = pd.to_datetime(
            df_datapoints['timestamp'], utc=True)
        df_datapoints = df_datapoints.set_index(
            pd.DatetimeIndex(df_datapoints['timestamp']))
        df_datapoints = df_datapoints.drop(columns=['timestamp'])
        # Scrub duplicates (these shouldn't exist)
        df_datapoints = df_datapoints[~df_datapoints.index.duplicated(
            keep='first')]
        # Fill in missing time indices
        df_datapoints = df_datapoints.reindex(datetimeindex)

    for idx_datetime, row in df_datapoints.iterrows():
        start_formatted_time = clean_pd_ts(idx_datetime)
        end_formatted_time = clean_pd_ts(idx_datetime + timedelta(seconds=10))
        output = os.path.join(target, f"{start_formatted_time}.video.mp4")

        if pd.isnull(row['data_id']):
            manifest.add_to_missing(output=output,
                                    start=start_formatted_time,
                                    end=end_formatted_time)
        else:
            manifest.add_to_download(bucketName=row["file"]["bucketName"],
                                     key=row["file"]["key"],
                                     output=output,
                                     start=start_formatted_time,
                                     end=end_formatted_time)

    return manifest
