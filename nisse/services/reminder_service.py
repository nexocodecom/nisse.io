import logging

import pytz

from nisse.services.user_service import *


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
                    user.__setattr__(value, self.native_time_to_utc(times_dic[key]))
                    contains_day_name = True

            # config string does not contains day name
            if not contains_day_name:
                time_from_param = self.native_time_to_utc(config)
                # set time Monday-Friday
                keys = ('mon', 'tue', 'wed', 'thu', 'fri')
                for key, value in self.user_reminder_time_column_day_map.items():
                    if key in keys:
                        user.__setattr__(value, time_from_param)
        except Exception as e:
            self.logger.warning('Incorrect format sent:{0} from user:{1}. Exception: {2}'.format(config, user, str(e)))
            return False

        self.user_service.update_remind_times(user)
        return True

    def native_time_to_utc(self, native_time):
        if isinstance(native_time, str):
            if native_time.lower() == 'off':
                return None
            native_time = datetime.strptime(native_time, "%H:%M").time()

        local_dt = pytz.timezone('Europe/Warsaw').localize(datetime.combine(datetime.utcnow(), native_time))
        utc_dt = local_dt.astimezone(pytz.UTC)

        return ReminderService.format_time(utc_dt.time())

    def utc_time_to_local_time_string(self, utc_time):
        if utc_time is None:
            return 'OFF'

        utc_dt = pytz.UTC.localize(datetime.combine(datetime.utcnow(), utc_time))
        user_dt = utc_dt.astimezone(self.get_user_tz())

        return ReminderService.format_time(user_dt.time())

    def get_user_tz(self):
        return pytz.timezone(self.time_zone_name)

    @staticmethod
    def format_time(time):
        return time.strftime("%H:%M")
