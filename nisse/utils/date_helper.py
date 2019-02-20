from calendar import monthrange
from datetime import datetime, date
from datetime import datetime as dt
from datetime import timedelta
from enum import Enum

from dateutil.easter import easter


class TimeRanges(Enum):
    today = 'Today'
    yesterday = 'Yesterday'
    this_2_week = 'This 2 weeks'
    previous_2_week = 'Previous 2 weeks'
    this_week = 'This week'
    previous_week = 'Previous week'
    this_month = 'This month'
    previous_month = 'Previous month'


def get_start_end_date(time_range_selected, base: datetime = None):
    if not base:
        base = dt.now().date()
    if time_range_selected == TimeRanges.yesterday.value:
        start = end = base - timedelta(1)
    elif time_range_selected == TimeRanges.this_week.value:
        start = base - timedelta(days=base.weekday())
        end = start + timedelta(6)
    elif time_range_selected == TimeRanges.previous_week.value:
        start = base - timedelta(days=base.weekday() + 7)
        end = start + timedelta(6)
    elif time_range_selected == TimeRanges.this_2_week.value:
        start = base - timedelta(days=base.weekday() + 7)
        end = start + timedelta(13)
    elif time_range_selected == TimeRanges.previous_2_week.value:
        start = base - timedelta(days=base.weekday() + 14)
        end = start + timedelta(13)
    elif time_range_selected == TimeRanges.this_month.value:
        start = dt(base.year, base.month, 1).date()
        end = dt(base.year, base.month, monthrange(base.year, base.month)[1]).date()
    elif time_range_selected == TimeRanges.previous_month.value:
        prev_month = 12 if base.month == 1 else base.month - 1
        year = base.year - 1 if base.month == 1 else base.year
        start = dt(year, prev_month, 1).date()
        end = dt(year, prev_month, monthrange(year, prev_month)[1]).date()
    else:
        start = end = base

    end = base if end > base else end

    return start, end


def get_float_duration(hours, minutes):
    return hours + minutes/60


def date_range(start_date, end_date):
    for n in range(int ((end_date - start_date).days)):
        yield start_date + timedelta(n)


def is_weekend(day):
    return day.weekday() >= 5 or is_holiday_poland(day)


def is_holiday_poland(day: date):
    est = easter(day.year)
    return day in [
        parse_formatted_date('{0}-01-01'.format(day.year)),
        parse_formatted_date('{0}-01-06'.format(day.year)),
        parse_formatted_date('{0}-05-01'.format(day.year)),
        parse_formatted_date('{0}-05-03'.format(day.year)),
        parse_formatted_date('{0}-08-15'.format(day.year)),
        parse_formatted_date('{0}-11-01'.format(day.year)),
        parse_formatted_date('{0}-11-11'.format(day.year)),
        parse_formatted_date('{0}-12-25'.format(day.year)),
        parse_formatted_date('{0}-12-26'.format(day.year)),
        est + timedelta(days=1)
    ]


def parse_formatted_date(date):
    return parse_formatted_datetime(date).date()


def parse_formatted_datetime(date):
    return datetime.strptime(date, '%Y-%m-%d')