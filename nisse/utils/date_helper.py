from calendar import monthrange
from datetime import timedelta
from datetime import datetime as dt
from enum import Enum

class TimeRanges(Enum):
    today = 'Today'
    yesterday = 'Yesterday'
    this_week = 'This week'
    previous_week = 'Previous week'
    this_month = 'This month'
    previous_month = 'Previous month'

def get_start_end_date(time_range_selected):
    now = dt.now()

    if time_range_selected == TimeRanges.yesterday.value:
        start = end = now.date() - timedelta(1)
    elif time_range_selected == TimeRanges.this_week.value:
        start = now.date() - timedelta(days=now.date().weekday())
        end = start + timedelta(6)
    elif time_range_selected == TimeRanges.previous_week.value:
        start = now.date() - timedelta(days=now.date().weekday() + 7)
        end = start + timedelta(6)
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
