import logging
from nisse.services.user_service import *
from dateutil import tz
import pytz
import datetime


class ReminderService(object):
    @inject
    def __init__(self, user_service: UserService, logger: logging.Logger, time_zone_name: str):
        self.user_service = user_service
        self.logger = logger
        self.time_zone_name = time_zone_name
        self.user_reminder_time_column_day_map = {'mon': 'remind_time_monday',
                                                  'tue': 'remind_time_tuesday',
                                                  'wed': 'remind_time_wednesday',
                                                  'thu': 'remind_time_thursday',
                                                  'fri': 'remind_time_friday',
                                                  'sat': 'remind_time_saturday',
                                                  'sun': 'remind_time_sunday'
                                                  }

    def get_user_reminder_config(self, user):
        return ('Monday '+self.utc_time_to_local_time_string(user.remind_time_monday),
                'Tuesday '+self.utc_time_to_local_time_string(user.remind_time_tuesday),
                'Wednesday '+self.utc_time_to_local_time_string(user.remind_time_wednesday),
                'Thursday '+self.utc_time_to_local_time_string(user.remind_time_thursday),
                'Friday '+self.utc_time_to_local_time_string(user.remind_time_friday),
                'Saturday '+self.utc_time_to_local_time_string(user.remind_time_saturday),
                'Sunday '+self.utc_time_to_local_time_string(user.remind_time_sunday))

    def set_user_reminder_config(self, user, config):
        contains_day_name = False
        try:
            times_dic = {day[:3]: day[4:] for day in config.split(';')}
            for key, value in self.user_reminder_time_column_day_map.items():
                if key in times_dic:
                    user.__setattr__(value, self.naive_time_to_utc(times_dic[key]))
                    contains_day_name = True

            # config string does not contains day name
            if not contains_day_name:
                time_from_param = self.naive_time_to_utc(config)
                # set time Monday-Friday
                keys = ('mon', 'tue', 'wed', 'thu', 'fri')
                for key, value in self.user_reminder_time_column_day_map.items():
                    if key in keys:
                        user.__setattr__(value, time_from_param)
        except Exception as e:
            self.logger.warning('Incorrect format sent:{0} from user:{1}. Exception: '.format(config, user, str(e)))
            return False

        self.user_service.update_remind_times(user)
        return True

    def naive_time_to_utc(self, naive):
        if isinstance(naive, str):
            if naive.lower() == 'off':
                return None
            naive = datetime.datetime.strptime(naive, "%H:%M")

        # find current date in user time
        from_zone = tz.gettz('UTC')
        user_zone = pytz.timezone(self.time_zone_name)
        utc = datetime.datetime.utcnow()
        utc = utc.replace(tzinfo=from_zone)
        user_time = utc.astimezone(user_zone)

        # create time based on current date and time stripped from string
        naive = datetime.datetime.combine(user_time.date(), naive.time())

        # convert local time into UTC
        user_dt = user_zone.localize(naive, is_dst=None)
        utc_dt = user_dt.astimezone(pytz.utc)

        return utc_dt.time()

    def utc_time_to_local_time_string(self, utc):
        if utc is None:
            return 'OFF'

        # find current date in local time
        from_zone = pytz.timezone("UTC")
        user_zone = pytz.timezone(self.time_zone_name)
        now = datetime.datetime.utcnow()
        user_time = now.astimezone(user_zone)

        # create time based on current date and time stripped from string
        naive = datetime.datetime.combine(user_time.date(), utc)

        # convert local time into local zone
        utc_dt = from_zone.localize(naive, is_dst=None)
        user_dt = utc_dt.astimezone(user_zone)

        return user_dt.time().strftime("%H:%M")
