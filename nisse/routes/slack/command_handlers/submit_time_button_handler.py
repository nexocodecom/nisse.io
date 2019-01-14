import logging

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.slack.dialog import Dialog
from nisse.models.slack.payload import RemindTimeReportBtnPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.routes.slack.command_handlers.submit_time_command_handler import SubmitTimeCommandHandler
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService


class SubmitTimeButtonHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService, submit_time_command_handler: SubmitTimeCommandHandler):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)
        self.submit_time_command_handler = submit_time_command_handler

    def handle(self, payload: RemindTimeReportBtnPayload):
        command_body_from_form_payload = {'trigger_id': payload.trigger_id, 'user_id': payload.user.id}
        action = next(iter(payload.actions.values()))
        self.submit_time_command_handler.show_dialog(command_body_from_form_payload, None, action)

    def create_dialog(self, command_body, argument, action) -> Dialog:
        raise NotImplementedError()
