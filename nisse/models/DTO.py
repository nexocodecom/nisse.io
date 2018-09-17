import datetime
from typing import NamedTuple


class PrintParametersDto(object):
    def __init__(self):
        self.user_id = None
        self.project_id = None
        self.date_from = None
        self.date_to = None


class TimeRecordDto(NamedTuple):
    day: str
    hours: int
    minutes: int
    comment: str
    project: str
    user_id: str

    def get_parsed_date(self):
        return datetime.datetime.strptime(self.day, '%Y-%m-%d').date()
