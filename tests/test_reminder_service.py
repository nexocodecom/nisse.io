import datetime
import logging
import unittest

import mock
import pytz

from nisse.models import User
from nisse.services.reminder_service import ReminderService


def get_mocked_user():
    mock_user = User()
    mock_user.user_id = 1
    mock_user.username = "user@mail.com"
    mock_user.first_name = "User Name"
    return mock_user


class ReminderServiceTests(unittest.TestCase):
    @mock.patch('nisse.services.UserService')
    def setUp(self,  mock_user_service):
        self.mock_user_service = mock_user_service

    def test_set_reminder_when_day_set_should_set_time_with_weekdays(self):
        # Arrange
        service = ReminderService(self.mock_user_service, logging.getLogger(), 'Europe/Warsaw')
        mocked_user = get_mocked_user()
        # Act
        service.set_user_reminder_config(mocked_user, 'mon:15:12')
        # Assert
        self.assertIsNotNone(mocked_user.remind_time_monday)
        self.assertIsNone(mocked_user.remind_time_tuesday)

    def test_set_reminder_when_only_time_provided_should_set_time_from_monday_till_friday(self):
        # Arrange
        service = ReminderService(self.mock_user_service, logging.getLogger(), 'Europe/Warsaw')
        mocked_user = get_mocked_user()
        # Act
        service.set_user_reminder_config(mocked_user, '15:00')
        # Assert
        self.assertIsNotNone(mocked_user.remind_time_monday)
        self.assertIsNotNone(mocked_user.remind_time_tuesday)
        self.assertIsNotNone(mocked_user.remind_time_wednesday)
        self.assertIsNotNone(mocked_user.remind_time_thursday)
        self.assertIsNotNone(mocked_user.remind_time_friday)
        self.assertIsNone(mocked_user.remind_time_saturday)
        self.assertIsNone(mocked_user.remind_time_sunday)

    def test_naive_time_to_utc_should_convert_time_correctly(self):
        # Arrange
        service = ReminderService(self.mock_user_service, logging.getLogger(), 'Europe/Warsaw')

        date_dst = datetime.datetime(1900, 1, 1, 13, 0)
        hours_offset = datetime.datetime.utcnow().astimezone(pytz.timezone('Europe/Warsaw')).utcoffset()

        # Act, Assert
        time = service.native_time_to_utc((date_dst + hours_offset).time())
        self.assertEqual(time, date_dst.time().strftime("%H:%M"))

        # Act, Assert
        time = service.native_time_to_utc('Off')
        self.assertEqual(time, None)

    def test_utc_time_to_local_time_string_should_return_correct_string(self):
        # Arrange
        date_obj = datetime.datetime(1900, 1, 1, 13, 0)
        service = ReminderService(self.mock_user_service, logging.getLogger(),'Europe/Warsaw')
        time = service.utc_time_to_local_time_string(date_obj.time())
        hours_offset = datetime.datetime.utcnow().astimezone(pytz.timezone('Europe/Warsaw')).utcoffset()
        # Assert
        self.assertEqual(time, (date_obj + hours_offset).strftime("%H:%M"))
