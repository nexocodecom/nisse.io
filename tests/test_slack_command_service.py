import logging
import time
import unittest
from datetime import datetime
from decimal import Decimal

import mock
from flask.config import Config

from nisse.models.DTO import TimeRecordDto
from nisse.models.database import Project, User, TimeEntry
from nisse.routes.slack.command_handlers.submit_time_command_handler import SubmitTimeCommandHandler
from nisse.services.reminder_service import ReminderService
from nisse.utils.date_helper import TimeRanges, get_start_end_date


def get_mocked_user():
    mock_user = mock.create_autospec(User)
    mock_user.user_id = 1
    mock_user.username = "user@mail.com"
    mock_user.first_name = "User Name"
    mock_user.user_projects = [Project(name='TestPr', project_id=1)]
    return mock_user


def get_mocked_time_entry():
    mock_time_entry = mock.create_autospec(TimeEntry)
    mock_time_entry.report_date = datetime(2018, 5, 1)
    mock_time_entry.comment = "comment"
    mock_time_entry.duration = Decimal('8.0')
    mock_time_entry.project = Project(name='TestPr', project_id=1)
    return mock_time_entry


class SlackCommandServiceTests(unittest.TestCase):

    @mock.patch('nisse.services.ProjectService')
    @mock.patch('nisse.services.UserService')
    @mock.patch('slackclient.SlackClient')
    @mock.patch('flask.config.Config')
    def setUp(self, mock_project_service, mock_user_service, mock_slack_client, config_mock):
        self.mock_user_service = mock_user_service
        self.mock_project_service = mock_project_service
        self.mock_slack_client = mock_slack_client
        self.config_mock = config_mock

        self.mock_project_service.get_projects.return_value = [Project(name='TestPr', project_id=1),
                                                               Project(name='TestPr2', project_id=2)]
        self.mock_project_service.get_project_by_id.return_value = None
        self.mock_user_service.get_user_by_id.return_value = None

        self.handler = SubmitTimeCommandHandler(mock.create_autospec(Config),
                                                mock.create_autospec(logging.Logger),
                                                mock_user_service,
                                                mock_slack_client,
                                                mock_project_service,
                                                mock.create_autospec(ReminderService))

    def test_submit_time_dialog_for_new_user_should_call_slack_api_and_return(self):
        # arrange
        def slack_client_api_call_side_effect(method, **kwargs):
            if method == "users.info":
                return {
                    "ok": True,
                    "user": {
                        "profile": {
                            "email": "user@mail.com",
                            "real_name_normalized": "User Name"
                        }
                    }
                }
            if method == "dialog.open":
                return {
                    "ok": True
                }

        self.mock_slack_client.api_call.side_effect = slack_client_api_call_side_effect
        command_body = {
            'trigger_id': '123abc',
            'user_id': 'user123'
        }
        action = mock.MagicMock()
        action.value.return_value = '2019-01-16'

        self.mock_project_service.get_projects.return_value = [Project(), Project()]
        self.mock_project_service.get_projects_by_user.return_value = [Project(), Project()]

        # act
        self.handler.show_dialog(command_body, None, action)

        # assert
        self.assertEqual(self.mock_slack_client.api_call.call_count, 1)        

    def test_submit_time_dialog_for_existed_user_should_set_default_project(self):
        # arrange
        def slack_client_api_call_side_effect(method, **kwargs):
            if method == "users.info":
                return {
                    "ok": True,
                    "user": {
                        "profile": {
                            "email": "user@mail.com",
                            "real_name_normalized": "User Name"
                        }
                    }
                }
            if method == "dialog.open":
                self.dialog = kwargs["dialog"]
                return {
                    "ok": True
                }

        self.mock_slack_client.api_call.side_effect = slack_client_api_call_side_effect
        self.mock_user_service.add_user.return_value = get_mocked_user()
        self.mock_user_service.get_user_by_email.return_value = get_mocked_user()
        users_last_time_entry = get_mocked_time_entry()
        self.mock_user_service.get_user_last_time_entry.return_value = users_last_time_entry
        command_body = {
            "trigger_id": "123abc",
            "user_id": "user123"
        }
        action = mock.MagicMock()
        action.value.return_value = '2019-01-16'

        self.mock_project_service.get_projects.return_value = [Project(), Project()]
        self.mock_project_service.get_projects_by_user.return_value = [Project(), Project()]

        # act
        self.handler.show_dialog(command_body, None, action)

        # assert
        self.assertEqual(self.mock_slack_client.api_call.call_count, 1)        
        # check selected project for dialog
        self.assertEqual(int(self.dialog["elements"][0]["value"]), users_last_time_entry.project.project_id)

    def test_save_submitted_time_should_add_user_if_not_exist(self):
        # arrange
        def slack_client_api_call_side_effect(method, **kwargs):
            if method == "users.info":
                return {
                    "ok": True,
                    "user": {
                        "profile": {
                            "email": "user@mail.com",
                            "real_name_normalized": "User Name"
                        },
                        "is_owner": True
                    }
                }
            if method == "chat.postMessage":
                return {
                    "ok": True
                }
            if method == "im.open":
                return {
                    "ok": True,
                    "channel": {"id": "DC123"}
                }

        self.mock_slack_client.api_call.side_effect = slack_client_api_call_side_effect
        self.mock_user_service.get_user_by_email.return_value = None
        self.mock_project_service.assign_user_to_project.return_value = None
        mock_user = get_mocked_user()
        mock_user.projects = []
        self.mock_user_service.add_user.return_value = mock_user

        time_record = TimeRecordDto(
            day="2018-05-15",
            hours=-1,
            minutes=0,
            comment="comment",
            project="1",
            user_id="usr1"
        )

        # act
        self.handler.save_submitted_time_task(time_record)

        # assert        
        time.sleep(0.5)
        self.mock_project_service.assign_user_to_project.assert_called_once()
        self.assertEqual(2, self.mock_slack_client.api_call.call_count)

    def test_save_submitted_time_should_return_error_if_exceed_daily_hours_limit(self):
        # arrange
        sent_chat_msgs = []

        def slack_client_api_call_side_effect(method, **kwargs):
            if method == "users.info":
                return {
                    "ok": True,
                    "user": {
                        "profile": {
                            "email": "user@mail.com",
                            "real_name_normalized": "User Name"
                        },
                        "is_owner": True
                    }
                }
            if method == "chat.postMessage":
                sent_chat_msgs.append(kwargs['text'])
                return {
                    "ok": True
                }
            if method == "im.open":
                return {
                    "ok": True,
                    "channel": {"id": "DC123"}
                }

        self.mock_slack_client.api_call.side_effect = slack_client_api_call_side_effect
        self.mock_user_service.get_user_by_email.return_value = get_mocked_user()
        self.mock_user_service.get_user_time_entries.return_value = [get_mocked_time_entry(), get_mocked_time_entry()]

        time_record = TimeRecordDto(
            day="2018-05-15",
            hours=8,
            minutes=15,
            comment="comment",
            project="1",
            user_id="usr1"
        )

        # act
        self.handler.save_submitted_time_task(time_record)

        # assert        
        time.sleep(0.5)
        self.assertEqual(len(sent_chat_msgs), 1)
        self.assertEqual(sent_chat_msgs[0], "Sorry, but You can't submit more than 24 hours for one day.")
    
    def test_get_start_end_date_should_return_correct_start_end_date(self):
        # arrange
        date = datetime(2018, 5, 14).date()

        # act
        today_start_end = get_start_end_date(TimeRanges.today.value, date)
        yesterday_start_end = get_start_end_date(TimeRanges.yesterday.value, date)
        this_week_start_end = get_start_end_date(TimeRanges.this_week.value, date)
        previous_week_start_end = get_start_end_date(TimeRanges.previous_week.value, date)
        this_month_start_end = get_start_end_date(TimeRanges.this_month.value, date)
        previous_month_start_end = get_start_end_date(TimeRanges.previous_month.value, date)
        
        # assert
        self.assertEqual(today_start_end, (datetime(2018, 5, 14).date(), datetime(2018, 5, 14).date()))
        self.assertEqual(yesterday_start_end, (datetime(2018, 5, 13).date(), datetime(2018, 5, 13).date()))
        self.assertEqual(this_week_start_end, (datetime(2018, 5, 14).date(), datetime(2018, 5, 14).date()))
        self.assertEqual(previous_week_start_end, (datetime(2018, 5, 7).date(), datetime(2018, 5, 13).date()))
        self.assertEqual(this_month_start_end, (datetime(2018, 5, 1).date(), datetime(2018, 5, 14).date()))
        self.assertEqual(previous_month_start_end, (datetime(2018, 4, 1).date(), datetime(2018, 4, 30).date()))
