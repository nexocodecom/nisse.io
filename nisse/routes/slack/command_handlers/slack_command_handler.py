from abc import ABC


from nisse.services.user_service import UserService
from nisse.services.project_service import Project, ProjectService
from nisse.services.reminder_service import ReminderService
from slackclient import SlackClient
import logging
from nisse.models.slack.payload import Payload
from nisse.services.exception import DataException, SlackUserException
from nisse.models.slack.dialog import Dialog
from datetime import datetime

USER_ROLE_USER = 'user'
USER_ROLE_ADMIN = 'admin'
DEFAULT_REMIND_TIME_FOR_NEWLY_ADDED_USER = "16:00"

class SlackCommandHandler(ABC):
    def __init__(self, logger: logging.Logger, user_service: UserService, slack_client: SlackClient, project_service: ProjectService, reminder_service: ReminderService):
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
