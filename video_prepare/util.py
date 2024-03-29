from datetime import datetime
import json
import os

import collections

try:
    collectionsAbc = collections.abc
except AttributeError:
    collectionsAbc = collections

import pytz


from dateutil.parser import parse as date_time_parse


def str_to_date(date_str):
    if isinstance(date_str, datetime):
        return date_str.astimezone(pytz.utc)

    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%zZ"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=pytz.UTC)
        except ValueError:
            pass

    return date_time_parse(date_str).replace(tzinfo=pytz.UTC)


def date_to_day_format(day):
    return datetime.strptime(day, "%Y-%m-%d")


def date_to_video_history_format(date):
    d = str_to_date(date)
    return d.isoformat(sep="T", timespec="seconds")


def create_dir(dir_path):
    directory = os.path.dirname(dir_path)
    os.makedirs(directory, exist_ok=True)


def format_frames(count):
    full = count // 10
    part = count % 10
    return f"{full:02}.{part}00"


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)


def vts(frames):
    total_seconds = frames // 10
    fractional = frames % 10
    total_minutes = total_seconds // 60
    hours = total_minutes // 60
    minutes = total_minutes - (hours * 60)
    seconds = total_seconds - (total_minutes * 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{fractional}00"


def clean_pd_ts(ts):
    return ts.to_pydatetime().astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Thanks: https://github.com/kkroening/ffmpeg-python/issues/450
def convert_kwargs_to_cmd_line_args(kwargs):
    """Helper function to build command line arguments out of dict."""
    args = []
    for k in sorted(kwargs.keys()):
        v = kwargs[k]
        if isinstance(v, collectionsAbc.Iterable) and not isinstance(v, str):
            for value in v:
                args.append("-{}".format(k))
                if value is not None:
                    args.append("{}".format(value))
            continue
        args.append("-{}".format(k))
        if v is not None:
            args.append("{}".format(v))
    return args
