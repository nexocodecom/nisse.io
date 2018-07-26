import logging
import time
import unittest
from datetime import datetime
import mock
from nisse.models.database import Project, User, TimeEntry
from nisse.services import SlackCommandService
from nisse.services.reminder_service import ReminderService
from nisse.services.report_service import ReportService
from nisse.services.slack.slack_command_service import TimeRanges
from decimal import *

from nisse.services.xlsx_document_service import XlsxDocumentService


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
    def setUp(self, mock_project_service, mock_user_service, mock_slack_client):
        self.mock_user_service = mock_user_service
        self.mock_project_service = mock_project_service
        self.mock_slack_client = mock_slack_client

        self.mock_project_service.get_projects.return_value = [Project(name='TestPr', project_id=1),
                                                               Project(name='TestPr2', project_id=2)]
        self.mock_project_service.get_project_by_id.return_value = None
        self.mock_user_service.get_user_by_id.return_value = None

        self.slack_command_service = SlackCommandService(logging.getLogger(),
                                                         mock_project_service,
                                                         mock_user_service,
                                                         mock_slack_client,
                                                         mock.create_autospec(ReportService),
                                                         mock.create_autospec(XlsxDocumentService),
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
            "trigger_id": "123abc",
            "user_id": "user123"
        }

        # act
        result = self.slack_command_service.submit_time_dialog(command_body)

        # assert
        self.assertEqual(self.mock_slack_client.api_call.call_count, 2)
        self.assertEqual(result, (None, 204))

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

        # act
        result = self.slack_command_service.submit_time_dialog(command_body)

        # assert
        self.assertEqual(self.mock_slack_client.api_call.call_count, 2)
        self.assertEqual(result, (None, 204))
        # check selected project for dialog
        self.assertEqual(self.dialog["elements"][0]["value"], users_last_time_entry.project.project_id)

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
        message_body = {
            "user": {"id": "usr1"},
            "channel": {"id": "ch1"},
            "command": "/ni",
            "submission": {
                "day": "2018-05-15",
                "duration": "8",
                "comment": "tasks done",
                "project": "1"
            }
        }
        # act
        result = self.slack_command_service.save_submitted_time(message_body)
        # assert
        self.assertEqual((None, 204), result)
        time.sleep(0.5)
        self.mock_user_service.add_user.assert_called_once()
        self.assertEqual(3, self.mock_slack_client.api_call.call_count)

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
        message_body = {
            "user": {"id": "usr1"},
            "channel": {"id": "ch1"},
            "command": "/ni",
            "submission": {
                "day": "2018-05-15",
                "duration": "8",
                "comment": "tasks done",
                "project": "1"
            }
        }
        # act
        result = self.slack_command_service.save_submitted_time(message_body)
        # assert
        self.assertEqual(result, (None, 204))
        time.sleep(0.5)
        self.assertEqual(len(sent_chat_msgs), 1)
        self.assertEqual(sent_chat_msgs[0], "Sorry, but You can't submit more than 20 hours for one day.")

    def test_save_submitted_time_should_return_error_if_negative_hour(self):
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
        self.mock_user_service.get_user_by_email.return_value = get_mocked_user()
        self.mock_user_service.get_user_time_entries.return_value = [get_mocked_time_entry(), get_mocked_time_entry()]
        message_body = {
            "user": {"id": "usr1"},
            "channel": {"id": "ch1"},
            "command": "/ni",
            "submission": {
                "day": "2018-05-15",
                "duration": "-1",
                "comment": "tasks done",
                "project": "1"
            }
        }
        # act
        result = self.slack_command_service.save_submitted_time(message_body)
        # assert
        self.assertEqual(result, ({
                                      "errors": [
                                          {
                                              "name": "duration",
                                              "error": "Use numbers, e.g. 2 or 2.5 or 2.45 etc"
                                          }
                                      ]
                                  }, 200))

    def test_list_command_time_range_selected_without_user_param_should_return_message(self):
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
            if method == "chat.postEphemeral":
                return {
                    "ok": True
                }

        self.mock_slack_client.api_call.side_effect = slack_client_api_call_side_effect

        mock_user = get_mocked_user()
        self.mock_user_service.get_user_by_email.return_value = mock_user
        self.mock_user_service.get_user_time_entries.return_value = [get_mocked_time_entry(), get_mocked_time_entry()]
        message_body = {
            "user": {"id": "usr1"},
            "channel": {"id": "ch1"},
            "actions": [{"selected_options": [{"value": TimeRanges.today.value}], "name": "usr1"}]
        }
        # act
        result = self.slack_command_service.list_command_time_range_selected(message_body)
        # assert
        self.assertEqual(result[0]["text"], "These are hours submitted by *You* for `" + TimeRanges.today.value + "`")
        self.assertEqual(len(result[0]["attachments"]), 2)
        self.assertEqual(result[0]["attachments"][0]["title"], "TestPr")

    def test_get_start_end_date_should_return_correct_start_end_date(self):
        # arrange
        with mock.patch('nisse.services.slack.slack_command_service.dt') as mock_datetime:
            mock_datetime.now.return_value = datetime(2018, 5, 14)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # act
            today_start_end = SlackCommandService.get_start_end_date(TimeRanges.today.value)
            yesterday_start_end = SlackCommandService.get_start_end_date(TimeRanges.yesterday.value)
            this_week_start_end = SlackCommandService.get_start_end_date(TimeRanges.this_week.value)
            previous_week_start_end = SlackCommandService.get_start_end_date(TimeRanges.previous_week.value)
            this_month_start_end = SlackCommandService.get_start_end_date(TimeRanges.this_month.value)
            previous_month_start_end = SlackCommandService.get_start_end_date(TimeRanges.previous_month.value)

            # assert
            self.assertEqual(today_start_end, (datetime(2018, 5, 14).date(), datetime(2018, 5, 14).date()))
            self.assertEqual(yesterday_start_end, (datetime(2018, 5, 13).date(), datetime(2018, 5, 13).date()))
            self.assertEqual(this_week_start_end, (datetime(2018, 5, 14).date(), datetime(2018, 5, 20).date()))
            self.assertEqual(previous_week_start_end, (datetime(2018, 5, 7).date(), datetime(2018, 5, 13).date()))
            self.assertEqual(this_month_start_end, (datetime(2018, 5, 1).date(), datetime(2018, 5, 31).date()))
            self.assertEqual(previous_month_start_end, (datetime(2018, 4, 1).date(), datetime(2018, 4, 30).date()))
