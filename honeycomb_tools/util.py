from datetime import datetime
from dateutil.parser import parse as date_time_parse
import os
import pytz


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
    return d.isoformat(sep='T', timespec='seconds')


def create_dir(dir_path):
    directory = os.path.dirname(dir_path)
    os.makedirs(directory, exist_ok=True)


def format_frames(count):
    full = count // 10
    part = count % 10
    return f"{full:02}.{part}00"
