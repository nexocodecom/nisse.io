from nisse.models import TimeEntry
from datetime import datetime as dt
from datetime import timedelta
from nisse.models import User


def get_full_class_name(obj):
    return obj.__module__ + "." + obj.__qualname__


def make_time_string(time_entry: TimeEntry):
    return "`" + format_slack_date(time_entry.report_date) + "`" + \
           " *" + format_duration_decimal(time_entry.duration) + "h*  _" + \
           (time_entry.comment[:60] + "..." if len(time_entry.comment) > 30 else time_entry.comment) + "_"


def make_option_time_string(time_entry: TimeEntry):
    return time_entry.report_date.strftime("%Y-%m-%d") + \
           " " + str(round(time_entry.duration, 2)) + "h " + \
           (time_entry.comment[:45] + "..." if len(time_entry.comment) > 15 else time_entry.comment)


def format_slack_date(date_to_format):
    return date_to_format.strftime("%b %d %a")


def format_duration_decimal(duration_float):
    ts = timedelta(hours=float(duration_float)).total_seconds()
    return str(int(ts/3600)) + ":" + str(int(ts % 3600 / 60)).zfill(2)


def generate_xlsx_file_name(user: User, project_name, date_from, date_to):
    return str(str(get_user_name(user) + "-" + project_name + "-").lower().replace(" ", "-")
                    + format_date_str(date_from) + "-"
                    + format_date_str(date_to) + ".xlsx")


def generate_xlsx_title(user: User, project_name, date_from, date_to):
    return str("Report for " + get_user_name(user)  + " (" + project_name + ") within "
                      + format_date_str(date_from) + " - "
                      + format_date_str(date_to))


def get_user_name(user: User):
    if user:
        user_name = user.first_name
        if user.last_name:
            user_name += (" " + user.last_name)
        return user_name
    else:
        return "all users"


def format_date_str(date):
    return format_date(dt.strptime(date, "%Y-%m-%d"))


def format_date(date):
    return date.strftime("%d-%b-%Y")