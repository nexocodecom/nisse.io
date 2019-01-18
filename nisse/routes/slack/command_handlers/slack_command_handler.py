import logging
from abc import ABC
from datetime import datetime
from typing import List

from flask.config import Config
from slackclient import SlackClient

from nisse.models.slack.common import LabelSelectOption
from nisse.models.slack.dialog import Dialog
from nisse.models.slack.message import TextSelectOption
from nisse.models.slack.payload import Payload
from nisse.services.exception import SlackUserException
from nisse.services.project_service import Project, ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService

USER_ROLE_USER = 'user'
USER_ROLE_ADMIN = 'admin'
DEFAULT_REMIND_TIME_FOR_NEWLY_ADDED_USER = "16:00"


class SlackCommandHandler(ABC):
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService, slack_client: SlackClient,
                 project_service: ProjectService, reminder_service: ReminderService):
        self.config = config
        self.user_service = user_service
        self.logger = logger
        self.slack_client = slack_client
        self.project_service = project_service
        self.reminder_service = reminder_service

    def get_user_by_slack_user_id(self, slack_user_id):

        user = self.user_service.get_user_by_slack_id(slack_user_id)

        if not user:
            slack_user_details = self.slack_client.api_call(
                "users.info",
                user=slack_user_id
            )

            if not slack_user_details['ok']:
                self.logger.error(
                    "Can't get user details. Error: " + slack_user_details.get("error"))
                raise SlackUserException(
                    'Retrieve slack user detail failed, user_id: ' + slack_user_id)

            user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                        slack_user_details['user']['profile']['real_name_normalized'],
                                        slack_user_id,
                                        slack_user_details['user']['is_owner'])
        return user

    def get_or_add_user(self, user_email, user_name, slack_user_id, is_owner=False):
        user = self.user_service.get_user_by_email(user_email)
        if user is None:
            user_role = USER_ROLE_ADMIN if is_owner else USER_ROLE_USER
            names = user_name.split(" ")
            first_name = names[0]
            last_name = None
            if len(names) > 1:
                last_name = names[1]
            user = self.user_service.add_user(
                user_email, first_name, last_name, self.user_service.get_default_password(), slack_user_id, user_role)
            self.project_service.assign_user_to_project(
                Project(project_id=1), user)
            self.reminder_service.set_user_reminder_config(
                user, DEFAULT_REMIND_TIME_FOR_NEWLY_ADDED_USER)
        return user

    def handle(self, payload: Payload):
        raise NotImplementedError()
    
    def create_dialog(self, command_body, argument, action) -> Dialog:
        raise NotImplementedError()

    def show_dialog(self, command_body, arguments, action):
        trigger_id = command_body['trigger_id']
        dialog = self.create_dialog(command_body, arguments, action).dump()

        resp = self.slack_client.api_call("dialog.open", trigger_id=trigger_id, dialog=dialog)
        if not resp["ok"]:
            self.logger.error("Can't open dialog submit time: " + resp.get("error"))

    def current_date(self) -> datetime:
        return datetime.now()

    def send_message_to_client(self, slack_user_id, message: str):
        im_channel = self.slack_client.api_call("im.open", user=slack_user_id)

        if not im_channel["ok"]:
            self.logger.error("Can't open im channel for: " + str(slack_user_id) + '. ' + im_channel["error"])
            return

        self.slack_client.api_call("chat.postMessage", channel=im_channel['channel']['id'], text=message, as_user=True)

    def get_default_project_id(self, first_id: str, user) -> str:
        if user is not None:
            user_last_time_entry = self.user_service.get_user_last_time_entry(user.user_id)
            if user_last_time_entry is not None:
                return user_last_time_entry.project.project_id

        return first_id

    def get_projects_option_list_as_text(self, user_id=None) -> List[TextSelectOption]:
        projects = self.project_service.get_projects_by_user(user_id) if user_id else self.project_service.get_projects()
        return [TextSelectOption(p.name, p.project_id) for p in projects]

    def get_projects_option_list_as_label(self, user_id=None) -> List[LabelSelectOption]:
        projects = self.project_service.get_projects_by_user(user_id) if user_id else self.project_service.get_projects()
        return [LabelSelectOption(p.name, p.project_id) for p in projects]

    def extract_slack_user_id(self, user):
        if user is not None and user.startswith("<") and user.endswith(">") and user[1] == "@":
            return user[2:-1].split('|')[0]
        else:
            return None
