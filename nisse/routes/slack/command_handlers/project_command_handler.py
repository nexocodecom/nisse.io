import logging
from typing import List

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.DTO import TimeRecordDto
from nisse.models.slack.common import ActionType
from nisse.models.slack.common import LabelSelectOption
from nisse.models.slack.dialog import Dialog, Element
from nisse.models.slack.message import Action
from nisse.models.slack.message import Attachment, Message, TextSelectOption
from nisse.models.slack.payload import ProjectPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.utils import string_helper


class ProjectCommandHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)

    def handle(self, payload: ProjectPayload) -> Dialog:

        if payload.submission:
            new_project_name: str = payload.submission.project_name
            new_project = self.project_service.create_project(new_project_name)
            user = self.user_service.get_user_by_id(int(payload.submission.user))
            self.project_service.assign_user_to_project(project=new_project, user=user)

            self.send_message_to_client(payload.user.id, "New project *{0}* has been successfully created!".format(new_project_name))

        else:
            action_name = next(iter(payload.actions))
            if action_name == 'projects_list':
                # handle assign user to project
                project = self.project_service.get_project_by_id(
                    payload.actions[action_name].selected_options[0].value)
                user = self.user_service.get_user_by_id(int(payload.submission.user))

    def create_dialog(self, command_body, argument, action):

        user = self.user_service.get_user_by_slack_id(command_body['user_id'])

        if user.role.role != 'admin':
            return Message(
                text="You have insufficient privileges... :neutral_face:",
                response_type="ephemeral",
                mrkdwn=True
            ).dump()

        users = self.user_service.get_users()
        user_options_list = [LabelSelectOption(label=string_helper.get_user_name(p), value=p.user_id) for p in users]

        elements: Element = [
            Element(label="Project name", type="text", name='project_name', placeholder="Specify project name"),
            Element(label="User", value=user.user_id,
                    type="select", name='user', placeholder="Select user", options=user_options_list)
        ]

        return Dialog(title="Create new project", submit_label="Create",
                                callback_id=string_helper.get_full_class_name(ProjectPayload),
                                elements=elements)

    def get_projects_option_list_as_label(self, user_id=None) -> List[LabelSelectOption]:
        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects_by_user(user_id) if user_id else self.project_service.get_projects()
        return [LabelSelectOption(p.name, p.project_id) for p in projects]

    def select_project(self, command_body, argument, action):

        user = self.user_service.get_user_by_slack_id(command_body['user_id'])
        project_options_list: List[TextSelectOption] = self.get_projects_option_list_as_text()
        user_default_project_id = self.get_default_project_id(project_options_list[0].value, user)

        return ProjectCommandHandler.create_select_project_message(user_default_project_id, project_options_list).dump()

    @staticmethod
    def create_select_project_message(user_default_project_id, project_options_list):
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
                callback_id=string_helper.get_full_class_name(ProjectPayload),
                actions=actions
            )
        ]
        return Message(
            text="I'm going to assign user to the project...",
            response_type="ephemeral",
            attachments=attachments
        )

    def save_submitted_time_task(self, time_record: TimeRecordDto):

        user = self.get_user_by_slack_user_id(time_record.user_id)

    def dispatch_project_command(self, command_body, arguments, action):
        if not arguments:
            return self.show_dialog(command_body, arguments, action)
        if arguments[0] == "assign":
            return self.select_project(command_body, arguments, action)