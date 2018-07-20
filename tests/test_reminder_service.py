import datetime
import unittest
import mock
import logging

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
        self.assertNotEqual(mocked_user.remind_time_monday, None)
        self.assertEqual(mocked_user.remind_time_tuesday, None)

    def test_set_reminder_when_only_time_provided_should_set_time_from_monday_till_friday(self):
        # Arrange
        service = ReminderService(self.mock_user_service, logging.getLogger(), 'Europe/Warsaw')
        mocked_user = get_mocked_user()
        # Act
        service.set_user_reminder_config(mocked_user, '15:00')
        # Assert
        self.assertNotEqual(mocked_user.remind_time_monday, None)
        self.assertNotEqual(mocked_user.remind_time_tuesday, None)
        self.assertNotEqual(mocked_user.remind_time_wednesday, None)
        self.assertNotEqual(mocked_user.remind_time_thursday, None)
        self.assertNotEqual(mocked_user.remind_time_friday, None)
        self.assertEqual(mocked_user.remind_time_saturday, None)
        self.assertEqual(mocked_user.remind_time_sunday, None)

    def test_naive_time_to_utc_should_convert_time_correctly(self):
        # Arrange
        service = ReminderService(self.mock_user_service, logging.getLogger(), 'Europe/Warsaw')

        # Act, Assert
        time = service.naive_time_to_utc('15:00')
        self.assertEqual(time, datetime.datetime(1900, 1, 1, 13, 0).time())

        # Act, Assert
        time = service.naive_time_to_utc('Off')
        self.assertEqual(time, None)

    def test_utc_time_to_local_time_string_should_return_correct_string(self):
        # Arrange
        service = ReminderService(self.mock_user_service, logging.getLogger(),'Europe/Warsaw')
        time = service.utc_time_to_local_time_string(datetime.datetime(1900, 1, 1, 13, 0).time())
        # Assert
        self.assertEqual(time, "15:00")