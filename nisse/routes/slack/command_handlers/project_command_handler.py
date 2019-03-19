import logging
from typing import List

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.slack.common import ActionType
from nisse.models.slack.dialog import Dialog, Element
from nisse.models.slack.message import Action
from nisse.models.slack.message import Attachment, Message, TextSelectOption
from nisse.models.slack.payload import ProjectAddPayload
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

    def handle(self, payload: ProjectAddPayload):

        if payload.submission:
            new_project_name: str = payload.submission.project_name
            self.project_service.create_project(new_project_name)

            self.send_message_to_client(payload.user.id,
                                        "New project *{0}* has been successfully created!".format(new_project_name))

        else:
            action: str = next(iter(payload.actions))
            action_name = action.split(":")[0]
            sub_action = action.split(":")[1]

            if action.startswith('projects_list'):
                # handle dialog with user selection
                project_id = payload.actions[action].selected_options[0].value
                users = []
                if sub_action == "unassign":
                    users = self.user_service.get_users_assigned_for_project(project_id)
                elif sub_action == "assign":
                    users = self.user_service.get_users_not_assigned_for_project(project_id)

                if not users:
                    return Message(text="There is no users to {0} :neutral_face:".format(sub_action),
                                   response_type="ephemeral", mrkdwn=True).dump()

                user_options_list = [TextSelectOption(string_helper.get_user_name(p), p.user_id) for p in users]

                return ProjectCommandHandler.create_select_user_message(sub_action, str(project_id),
                                                                        user_options_list).dump()

            elif action_name.startswith('assign'):
                # handle assign user to project
                project = self.project_service.get_project_by_id(sub_action)
                user = self.user_service.get_user_by_id(payload.actions[action].selected_options[0].value)

                self.project_service.assign_user_to_project(project=project, user=user)

                return Message(text="User *{0}* has been successfully assigned for project *{1}* :grinning:"
                               .format(string_helper.get_user_name(user), project.name),
                               response_type="ephemeral", mrkdwn=True).dump()

            elif action_name.startswith('unassign'):
                # handle unassign user to project
                project = self.project_service.get_project_by_id(sub_action)
                user = self.user_service.get_user_by_id(payload.actions[action].selected_options[0].value)

                self.project_service.unassign_user_from_project(project=project, user=user)

                return Message(text="User *{0}* has been successfully unassigned from project *{1}*"
                                        .format(string_helper.get_user_name(user), project.name),
                                        response_type="ephemeral", mrkdwn=True).dump()

    def create_dialog(self, command_body, argument, action):

        elements: Element = [
            Element(label="Project name", type="text", name='project_name', placeholder="Specify project name")
        ]

        return Dialog(title="Create new project", submit_label="Create",
                      callback_id=string_helper.get_full_class_name(ProjectAddPayload), elements=elements)

    def select_project(self, slack_user_id, arguments):

        user = self.get_user_by_slack_id(slack_user_id)
        project_options_list: List[TextSelectOption] = self.get_projects_option_list_as_text()
        user_default_project_id = self.get_default_project_id(project_options_list[0].value, user)

        return ProjectCommandHandler.create_select_project_message(str("projects_list:" + arguments[0]),
                                                                   user_default_project_id, project_options_list).dump()

    @staticmethod
    def create_select_project_message(action_name, user_default_project_id, project_options_list):
        actions = [
            Action(
                name=str(action_name),
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
                callback_id=string_helper.get_full_class_name(ProjectAddPayload),
                actions=actions
            )
        ]
        return Message(
            text="I'm going to (un)assign user to the project...",
            response_type="ephemeral",
            attachments=attachments
        )

    @staticmethod
    def create_select_user_message(action_name, subaction_name, user_options_list):
        actions = [
            Action(
                name=action_name + ":" + subaction_name,
                text="Select user...",
                type=ActionType.SELECT.value,
                options=user_options_list
            ),
        ]
        attachments = [
            Attachment(
                text="Select user for " + action_name + "...",
                fallback="Select user",
                color="#3AA3E3",
                attachment_type="default",
                callback_id=string_helper.get_full_class_name(ProjectAddPayload),
                actions=actions
            )
        ]
        return Message(
            text="",
            response_type="ephemeral",
            attachments=attachments
        )

    def dispatch_project_command(self, command_body, arguments, action):

        user = self.get_user_by_slack_id(command_body['user_id'])

        if user.role.role != 'admin':
            return Message(text="You have insufficient privileges to use this command... :neutral_face:",
                           response_type="ephemeral", mrkdwn=True).dump()

        if not arguments:
            return self.show_dialog(command_body, arguments, action)
        elif arguments[0] == "assign":
            return self.select_project(command_body['user_id'], arguments)
        elif arguments[0] == "unassign":
            return self.select_project(command_body['user_id'], arguments)
        else:
            return Message(text="Oops, I don't understand the command's parameters :thinking_face:",
                          response_type="ephemeral", mrkdwn=True ).dump()
