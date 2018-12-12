from nisse.routes.slack.command_handlers.dayoff_command_handler import DayOffCommandHandler
from nisse.models.slack.payload import RequestFreeDaysPayload, SlackUser, RequestFreeDaysForm
from nisse.services.reminder_service import ReminderService
from nisse.models.database import Dayoff
from marshmallow import ValidationError
from unittest import TestCase
from unittest.mock import MagicMock
from datetime import datetime
import logging
import mock


class TestDayOffCommanHandler(TestCase):

    @mock.patch('nisse.services.ProjectService')
    @mock.patch('nisse.services.UserService')
    @mock.patch('slackclient.SlackClient')
    @mock.patch('nisse.services.DayOffService')
    def setUp(self, mock_project_service, mock_user_service, mock_slack_client, mock_dayoff_service):
        self.mock_user_service = mock_user_service
        self.mock_project_service = mock_project_service
        self.mock_slack_client = mock_slack_client
        self.mock_dayoff_service = mock_dayoff_service

        self.mock_dayoff_service.get_user_days_off_since.return_value = [
            Dayoff(start_date=datetime(2018, 12, 12), end_date=datetime(2018, 12, 18))]

        self.mock_project_service.get_project_by_id.return_value = None
        self.mock_user_service.get_user_by_id.return_value = None

        self.handler = DayOffCommandHandler(mock.create_autospec(logging.Logger),
                                            mock_user_service,
                                            mock_slack_client,
                                            mock_project_service,
                                            mock.create_autospec(
                                                ReminderService),
                                            mock_dayoff_service)

    def test_new_daysoff_should_not_start_within_exisitng_daysoff(self):
        #Arrange
        request_form = RequestFreeDaysForm(start_date='2018-12-15', end_date='2018-12-19', reason='')
        payload = RequestFreeDaysPayload('', '', '', None, SlackUser('1', 'name'), None, '',  request_form)
        self.handler.current_date = MagicMock(return_value=datetime(2018, 12, 10))

        #Act        
        try:
            self.handler.handle(payload)
            self.fail()
        except ValidationError as err:
            self.assertEqual(err.messages, ['Day off must not start within other holiday'])
            self.assertEqual(err.field_names, ['start_date'])

    def test_new_daysoff_should_not_end_within_exisitng_daysoff(self):
        #Arrange
        request_form = RequestFreeDaysForm(start_date='2018-12-11', end_date='2018-12-15', reason='')
        payload = RequestFreeDaysPayload('', '', '', None, SlackUser('1', 'name'), None, '',  request_form)
        self.handler.current_date = MagicMock(return_value=datetime(2018, 12, 10))        

        #Act
        try:
            self.handler.handle(payload)
            self.fail()
        except ValidationError as err:
            self.assertEqual(err.messages, ['Day off must not end within other holiday'])
            self.assertEqual(err.field_names, ['end_date'])

    def test_new_daysoff_should_validate_current_date(self):
        #Arrange
        request_form = RequestFreeDaysForm(start_date='2018-12-10', end_date='2018-12-15', reason='')
        payload = RequestFreeDaysPayload('', '', '', None, SlackUser('1', 'name'), None, '',  request_form)
        self.handler.current_date = MagicMock(return_value=datetime(2018, 12, 10))        

        #Act
        try:
            self.handler.handle(payload)
            self.fail()
        except ValidationError as err:
            self.assertEqual(err.messages, ['Holiday must start in the future'])
            self.assertEqual(err.field_names, ['start_date'])

    def test_new_daysoff_should_check_if_start_date_is_not_lower_than_end_date(self):
        #Arrange
        request_form = RequestFreeDaysForm(start_date='2018-12-10', end_date='2018-12-9', reason='')
        payload = RequestFreeDaysPayload('', '', '', None, SlackUser('1', 'name'), None, '',  request_form)
        self.handler.current_date = MagicMock(return_value=datetime(2018, 12, 1))        

        #Act
        try:
            self.handler.handle(payload)
            self.fail()
        except ValidationError as err:
            self.assertEqual(err.messages, ['End date must not be lower than start date'])
            self.assertEqual(err.field_names, ['end_date'])
