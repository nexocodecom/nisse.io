from nisse.routes.slack.command_handlers.vacation_command_handler import VacationCommandHandler
from nisse.models.slack.payload import RequestFreeDaysPayload, SlackUser, RequestFreeDaysForm
from nisse.services.reminder_service import ReminderService
from nisse.models.database import Vacation
from marshmallow import ValidationError
from unittest import TestCase
from unittest.mock import MagicMock
from datetime import datetime
import logging
import mock


class TestVacationCommanHandler(TestCase):

    @mock.patch('nisse.services.ProjectService')
    @mock.patch('nisse.services.UserService')
    @mock.patch('slackclient.SlackClient')
    @mock.patch('nisse.services.VacationService')
    @mock.patch('nisse.services.GoogleCalendarService')
    def setUp(self, mock_project_service, mock_user_service, mock_slack_client, mock_vacation_service, mock_calendar_service):
        self.mock_user_service = mock_user_service
        self.mock_project_service = mock_project_service
        self.mock_slack_client = mock_slack_client
        self.mock_vacation_service = mock_vacation_service
        self.mock_calendar_service = mock_calendar_service

        self.mock_vacation_service.get_user_vacations_since.return_value = [
            Vacation(start_date=datetime(2018, 12, 12), end_date=datetime(2018, 12, 18))]

        self.mock_project_service.get_project_by_id.return_value = None
        self.mock_user_service.get_user_by_id.return_value = None

        self.handler = VacationCommandHandler(mock.create_autospec(logging.Logger),
                                            mock_user_service,
                                            mock_slack_client,
                                            mock_project_service,
                                            mock.create_autospec(ReminderService),
                                            mock_vacation_service,
                                            mock_calendar_service)

    def test_new_daysoff_should_not_start_within_exisitng_daysoff(self):
        #Arrange
        request_form = RequestFreeDaysForm(
            start_date='2018-12-15', end_date='2018-12-19', reason='')
        payload = RequestFreeDaysPayload(
            '', '', '', None, SlackUser('1', 'name'), None, '',  request_form)
        self.handler.current_date = MagicMock(
            return_value=datetime(2018, 12, 10))

        #Act
        try:
            self.handler.handle(payload)
            self.fail()
        except ValidationError as err:
            self.assertEqual(
                err.messages, ['Vacation must not start within other vacation. Conflicting vacation: 2018-12-12 to 2018-12-18'])
            self.assertEqual(err.field_names, ['start_date'])

    def test_new_daysoff_should_not_end_within_exisitng_daysoff(self):
        #Arrange
        request_form = RequestFreeDaysForm(
            start_date='2018-12-11', end_date='2018-12-15', reason='')
        payload = RequestFreeDaysPayload(
            '', '', '', None, SlackUser('1', 'name'), None, '',  request_form)
        self.handler.current_date = MagicMock(
            return_value=datetime(2018, 12, 10))

        #Act
        try:
            self.handler.handle(payload)
            self.fail()
        except ValidationError as err:
            self.assertEqual(
                err.messages, ['Vacation must not end within other vacation. Conflicting vacation: 2018-12-12 to 2018-12-18'])
            self.assertEqual(err.field_names, ['end_date'])

    def test_new_daysoff_should_validate_current_date(self):
        #Arrange
        request_form = RequestFreeDaysForm(
            start_date='2018-12-10', end_date='2018-12-15', reason='')
        payload = RequestFreeDaysPayload(
            '', '', '', None, SlackUser('1', 'name'), None, '',  request_form)
        self.handler.current_date = MagicMock(
            return_value=datetime(2018, 12, 10))

        #Act
        try:
            self.handler.handle(payload)
            self.fail()
        except ValidationError as err:
            self.assertEqual(
                err.messages, ['Vacation must start in the future'])
            self.assertEqual(err.field_names, ['start_date'])

    def test_new_daysoff_should_check_if_start_date_is_not_lower_than_end_date(self):
        #Arrange
        request_form = RequestFreeDaysForm(
            start_date='2018-12-10', end_date='2018-12-9', reason='')
        payload = RequestFreeDaysPayload(
            '', '', '', None, SlackUser('1', 'name'), None, '',  request_form)
        self.handler.current_date = MagicMock(
            return_value=datetime(2018, 12, 1))

        #Act
        try:
            self.handler.handle(payload)
            self.fail()
        except ValidationError as err:
            self.assertEqual(
                err.messages, ['End date must not be lower than start date'])
            self.assertEqual(err.field_names, ['end_date'])

    def test_should_succeed(self):
        #Arrange
        request_form = RequestFreeDaysForm(
            start_date='2018-12-19', end_date='2018-12-24', reason='')
        payload = RequestFreeDaysPayload(
            '', '', '', None, SlackUser('1', 'name'), None, '',  request_form)
        self.handler.current_date = MagicMock(
            return_value=datetime(2018, 12, 13))
        self.handler.get_user_by_slack_user_id = MagicMock()
        self.handler.send_message_to_client = MagicMock()

        #Act
        self.handler.handle(payload)

        #Assert
        self.assertEqual(1, self.handler.get_user_by_slack_user_id.call_count)
        self.assertEqual(1, self.mock_vacation_service.get_user_vacations_since.call_count)
        self.assertEqual(1, self.mock_vacation_service.insert_user_vacation.call_count)
        self.assertEqual(1, self.mock_calendar_service.report_free_day.call_count)
        self.assertEqual(1, self.handler.send_message_to_client.call_count)
        

