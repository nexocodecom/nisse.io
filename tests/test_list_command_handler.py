from nisse.routes.slack.command_handlers.list_command_handler import ListCommandHandler, ListCommandPayload
from nisse.models.slack.payload import RequestFreeDaysPayload, SlackUser, RequestFreeDaysForm
from nisse.services.reminder_service import ReminderService
from nisse.models.database import User, Project, TimeEntry
from nisse.models.slack.payload import Channel, Action, Option
from nisse.utils.date_helper import TimeRanges
from marshmallow import ValidationError
from unittest.mock import MagicMock
from unittest import TestCase
from datetime import datetime
from decimal import Decimal
import logging
import mock

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


class TestVacationCommanHandler(TestCase):

    @mock.patch('nisse.services.ProjectService')
    @mock.patch('nisse.services.UserService')
    @mock.patch('slackclient.SlackClient')
    @mock.patch('flask.config.Config')
    def setUp(self, mock_project_service, mock_user_service, mock_slack_client, config_mock):
        self.mock_user_service = mock_user_service
        self.mock_project_service = mock_project_service
        self.mock_slack_client = mock_slack_client
        self.config_mock = config_mock

        self.mock_project_service.get_project_by_id.return_value = None
        self.mock_user_service.get_user_by_id.return_value = None

        self.handler = ListCommandHandler(config_mock,
                                            mock.create_autospec(logging.Logger),
                                            mock_user_service,
                                            mock_slack_client,
                                            mock_project_service,
                                            mock.create_autospec(ReminderService))
    
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
                        },
                        "is_owner": True
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
        # message_body = {
        #     "user": {"id": "usr1"},
        #     "channel": {"id": "ch1"},
        #     "actions": [{"selected_options": [{"value": TimeRanges.today.value}], "name": "usr1"}]
        # }
        payload: ListCommandPayload = ListCommandPayload(None, None, None, None, SlackUser(id="usr1", name="Test Name"), Channel("id", "ch1"), None,
                                                         [Action("usr1", None, None, [Option(TimeRanges.today.value)])])
        # act
        result = self.handler.handle(payload)
        # assert
        self.assertEqual(result["text"], "These are hours submitted by *You* for `" + TimeRanges.today.value + "`")
        self.assertEqual(len(result["attachments"]), 3)
        self.assertEqual(result["attachments"][0]["title"], "TestPr")