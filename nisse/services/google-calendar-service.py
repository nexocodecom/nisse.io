from datetime import date, datetime
import oauth2client
import pytz
from nisse.utils.date_helper import 

from flask.config import Config
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from oauth2client.client import OAuth2WebServerFlow


class GoogleCalendarService(object):

    def __init__(self, config: Config):
        store = file.Storage('calendar-token.json')
        self.config = config
        self.creds = store.get()
        self.holiday_calendar_id = config['GOOGLE_HOLIDAY_CALENDAR_NAME']
        self.free_day_calendar_id = config['GOOGLE_CALENDAR_NAME']
        self.time_zone = config['USERS_TIME_ZONE']
        if not self.creds or self.creds.invalid:
            flow = self.create_flow(
                config['GOOGLE_API_CLIENT_ID'], config['GOOGLE_API_CLIENT_SECRET'], config['GOOGLE_CALENDAR_SCOPES'])
            self.creds = tools.run_flow(flow, store)
        self.service = build('calendar', 'v3', http=self.creds.authorize(Http()))

    def get_free_days(self, from_date: date, to_date: date):
        from_date_utc = self._convert_to_google_utc_date_string(from_date)
        to_date_utc = self._convert_to_google_utc_date_string(to_date)

        free_days_result = self.service.events() \
            .list(calendarId=self.holiday_calendar_id, timeMin=from_date_utc, timeMax=to_date_utc) \
            .execute()
        return free_days_result.get('items', [])

    def create_free_day(self, from_date: date, to_date: date, slack_user_name: str):
        start = {
            "": from_date.__format__("")
            "timeZone": self.time_zone
        }


        self.service.events().insert(
            
        )

    def _convert_to_google_utc_date_string(self, date: datetime):
        local_tz = pytz.timezone(self.config['USERS_TIME_ZONE'])
        naive_datetime = datetime(date.year(), date.month(), date.day())
        local_date = local_tz.localize(naive_datetime, self.is_dst())

        return local_date.astimezone(pytz.utc).isoformat() + "Z"

    def is_dst(self):
        """Determine whether or not Daylight Savings Time (DST)
        is currently in effect"""

        x = datetime(datetime.now().year, 1, 1, 0, 0, 0, tzinfo=pytz.timezone(self.time_zone)) # Jan 1 of this year
        y = datetime.now(pytz.timezone(self.time_zone))

        # if DST is in effect, their offsets will be different
        return not (y.utcoffset() == x.utcoffset())

    def create_flow(self, client_id, client_secret, scope):

        #stolen from internal google implementation client.py method: credentials_from_code
        return OAuth2WebServerFlow(client_id, client_secret, scope,
                                   redirect_uri='postmessage',
                                   user_agent=None,
                                   token_uri=oauth2client.GOOGLE_TOKEN_URI,
                                   auth_uri=oauth2client.GOOGLE_AUTH_URI,
                                   revoke_uri=oauth2client.GOOGLE_REVOKE_URI,
                                   device_uri=oauth2client.GOOGLE_DEVICE_URI,
                                   token_info_uri=oauth2client.GOOGLE_TOKEN_INFO_URI,
                                   pkce=False,
                                   code_verifier=None)
