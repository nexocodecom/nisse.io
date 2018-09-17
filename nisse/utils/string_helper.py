from nisse.models import TimeEntry
from datetime import datetime as dt
from datetime import timedelta


def get_full_class_name(obj):
    return obj.__module__ + "." + obj.__qualname__


def make_time_string(time_entry: TimeEntry):
    return format_slack_date(time_entry.report_date) + \
           " *" + format_duration_decimal(time_entry.duration) + "h*  _" + \
           (time_entry.comment[:60] + "..." if len(time_entry.comment) > 30 else time_entry.comment) + "_"


def make_option_time_string(time_entry: TimeEntry):
    return time_entry.report_date.strftime("%Y-%m-%d") + \
           " " + str(round(time_entry.duration, 2)) + "h " + \
           (time_entry.comment[:45] + "..." if len(time_entry.comment) > 15 else time_entry.comment)


def format_slack_date(date_to_format):
    return "<!date^" + str(
        dt.combine(date_to_format, dt.min.time()).timestamp()).rstrip('0').rstrip(
        '.') + \
           "^{date_short}|" + date_to_format.strftime("%Y-%m-%d") + ">"


def format_duration_decimal(duration_float):
    ts = timedelta(hours=float(duration_float)).total_seconds()
    return str(int(ts/3600)) + ":" + str(int(ts % 3600 / 60)).zfill(2)

