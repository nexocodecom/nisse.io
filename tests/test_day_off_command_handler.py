from nisse.routes.slack.command_handlers.dayoff_command_handler import DayOffCommandHandler
from unittest import TestCase
import mock


class TestDayOffCommanHandler(TestCase):

    @mock.patch('nisse.services.ProjectService')
    @mock.patch('nisse.services.UserService')
    def setUp(self, mock_project_service, mock_user_service):
        self.mock_user_service = mock_user_service
        self.mock_project_service = mock_project_service

        self.handler = DayOffCommandHandler()
