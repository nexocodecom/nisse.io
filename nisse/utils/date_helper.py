from calendar import monthrange
from datetime import timedelta
from datetime import datetime as dt
from enum import Enum
from datetime import datetime

class TimeRanges(Enum):
    today = 'Today'
    yesterday = 'Yesterday'
    this_2_week = 'This 2 weeks'
    previous_2_week = 'Previous 2 weeks'
    this_week = 'This week'
    previous_week = 'Previous week'
    this_month = 'This month'
    previous_month = 'Previous month'

def get_start_end_date(time_range_selected, now = dt.now()):
    if time_range_selected == TimeRanges.yesterday.value:
        start = end = now.date() - timedelta(1)
    elif time_range_selected == TimeRanges.this_week.value:
        start = now.date() - timedelta(days=now.date().weekday())
        end = start + timedelta(6)
    elif time_range_selected == TimeRanges.previous_week.value:
        start = now.date() - timedelta(days=now.date().weekday() + 7)
        end = start + timedelta(6)
    elif time_range_selected == TimeRanges.this_2_week.value:
        start = now.date() - timedelta(days=now.date().weekday() + 7)
        end = start + timedelta(13)
    elif time_range_selected == TimeRanges.previous_2_week.value:
        start = now.date() - timedelta(days=now.date().weekday() + 14)
        end = start + timedelta(13)
    elif time_range_selected == TimeRanges.this_month.value:
        start = dt(now.year, now.month, 1).date()
        end = dt(now.year, now.month, monthrange(now.year, now.month)[1]).date()
    elif time_range_selected == TimeRanges.previous_month.value:
        prev_month = 12 if now.month == 1 else now.month - 1
        year = now.year - 1 if now.month == 1 else now.year
        start = dt(year, prev_month, 1).date()
        end = dt(year, prev_month, monthrange(year, prev_month)[1]).date()
    else:
        start = end = now.date()

    return start, end


def get_float_duration(hours, minutes):
    return hours + minutes/60


def date_range(start_date, end_date):
    for n in range(int ((end_date - start_date).days)):
        yield start_date + timedelta(n)


def is_weekend(date):
    return date.weekday() >= 5

def parse_formatted_date(date):
    return parse_formatted_date(date).date()

def parse_formatted_datetime(date):
    return datetime.strptime(date, '%Y-%m-%d')

def is_dst(time_zone):
    """Determine whether or not Daylight Savings Time (DST)
    is currently in effect"""

    

    x = datetime(datetime.now().year, 1, 1, 0, 0, 0, tzinfo=pytz.timezone(
        self.config['USERS_TIME_ZONE']))  # Jan 1 of this year
    y = datetime.now(pytz.timezone(self.config['USERS_TIME_ZONE']))

    # if DST is in effect, their offsets will be different
    return not (y.utcoffset() == x.utcoffset())