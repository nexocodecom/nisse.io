from datetime import date, datetime
import pytz
import httplib2

from flask.config import Config
from googleapiclient.discovery import build
from flask_injector import inject
from nisse.services.oauth_store import OAuthStore
from nisse.utils.date_helper import parse_formatted_date


class GoogleCalendarService(object):

    @inject
    def __init__(self, config: Config, oauth_store: OAuthStore):
        self.config = config
        self.oauth_store = oauth_store
        self.holiday_calendar_id = config['GOOGLE_HOLIDAY_CALENDAR_NAME']
        self.free_day_calendar_id = config['GOOGLE_CALENDAR_NAME']
        self.time_zone = config['USERS_TIME_ZONE']
        self.calendar_title_format = config['CALENDAR_TITLE_FORMAT']

        self.service = build(
            'calendar', 'v3', credentials=oauth_store.get_credentials())

    def get_free_days(self, from_date: date, to_date: date):
        from_date_utc = self._convert_to_google_utc_date_string(from_date)
        to_date_utc = self._convert_to_google_utc_date_string(to_date)

        free_days_result = self.service.events() \
            .list(calendarId=self.holiday_calendar_id, timeMin=from_date_utc, timeMax=to_date_utc) \
            .execute()
        return free_days_result.get('items', [])

    def report_free_day(self, slack_user_name:str, user_email: str, from_date: date, to_date: date, reason:str):        
        calendar = self.get_calendar_by_name(self.free_day_calendar_id)
        if calendar is None:
            return False
        body = {
            'summary': self.calendar_title_format.format(slack_user_name),
            'start': {
                "date": self._format_google_date(from_date),
                "timeZone": self.time_zone
            },
            'end': {
                "date": self._format_google_date(to_date),
                "timeZone": self.time_zone
            },
            'creator': {
                "displayName": self.calendar_title_format.format(slack_user_name),
                "email": user_email
            },
            'description': reason
        }
        self.service.events().insert(calendarId=calendar['id'], body=body).execute()

    def get_calendars(self):
        calendars_dict_items = self.service.calendarList().list().execute()
        return dict(calendars_dict_items)['items']

    def get_calendar_by_name(self, calendar_name):
        calendars = self.get_calendars()
        filtered_calendars = list(filter(lambda x: x['summary'] == self.free_day_calendar_id, calendars))
        if len(filtered_calendars) == 0: 
            return None
        
        return filtered_calendars[0]

    def _format_google_date(self, date: date):
        return date.strftime('%Y-%m-%d')

    def _convert_to_google_utc_date_string(self, date: date):
        local_tz = pytz.timezone(self.config['USERS_TIME_ZONE'])
        naive_datetime = datetime(date.year(), date.month(), date.day())
        local_date = local_tz.localize(naive_datetime, self.is_dst())

        return local_date.astimezone(pytz.utc).isoformat() + "Z"

    def is_dst(self):
        """Determine whether or not Daylight Savings Time (DST)
        is currently in effect"""

        x = datetime(datetime.now().year, 1, 1, 0, 0, 0,
                     tzinfo=pytz.timezone(self.time_zone))  # Jan 1 of this year
        y = datetime.now(pytz.timezone(self.time_zone))

        # if DST is in effect, their offsets will be different
        return not (y.utcoffset() == x.utcoffset())
