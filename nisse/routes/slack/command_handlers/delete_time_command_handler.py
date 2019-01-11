import logging
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from flask_injector import inject
from flask.config import Config
from slackclient import SlackClient
from nisse.services.user_service import UserService
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.models.slack.payload import DeleteCommandPayload
from nisse.models.slack.dialog import Element, Dialog
from nisse.models.slack.message import Action, Attachment, Message, TextSelectOption
from typing import List
from nisse.models.slack.common import ActionType
from nisse.utils import string_helper

class DeleteTimeCommandHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)

    def handle(self, payload: DeleteCommandPayload):

        logging.info("payload")

    def create_dialog(self, command_body, argument, action) -> Dialog:

        user = self.user_service.get_user_by_slack_id(command_body['user_id'])

        project_options_list: List[TextSelectOption] = self.get_projects_option_list_as_text(user.user_id)
        user_default_project_id = self.get_default_project_id(project_options_list[0].value, user)

        actions = [
            Action(
                name="projects_list",
                text="Select project...",
                type=ActionType.SELECT.value,
                value=user_default_project_id,
                options=project_options_list
            ),
        ]
        attachments = [
            Attachment(
                text="Select project first",
                fallback="Select project",
                color="#3AA3E3",
                attachment_type="default",
                callback_id=string_helper.get_full_class_name(DeleteCommandPayload),
                actions=actions
            )
        ]
        message = Message(
            text="I'm going to remove time entry :wastebasket:...",
            response_type="ephemeral",
            attachments=attachments
        )

        return Dialog("Deleting time", "Delete", string_helper.get_full_class_name(DeleteTimeCommandHandler),
                      message)

    def get_projects_option_list_as_text(self, user_id=None) -> List[TextSelectOption]:
        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects_by_user(user_id) if user_id else self.project_service.get_projects()
        return [TextSelectOption(p.name, p.project_id) for p in projects]

