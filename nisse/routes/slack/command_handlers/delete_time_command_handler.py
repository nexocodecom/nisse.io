import logging
from typing import List

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models import TimeEntry
from nisse.models.slack.common import ActionType
from nisse.models.slack.dialog import Dialog
from nisse.models.slack.message import Action, Attachment, Message, TextSelectOption
from nisse.models.slack.payload import DeleteTimeEntryPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.utils import string_helper
from nisse.utils.validation_helper import list_find


class DeleteTimeCommandHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)

    def handle(self, payload: DeleteTimeEntryPayload):

        action_name = next(iter(payload.actions.keys()))
        action = next(iter(payload.actions.values()))
        user = self.get_user_by_slack_user_id(payload.user.id)

        if action_name == 'projects_list':
            # project selected
            project_id_selected = action.selected_options[0].value

            projects = self.project_service.get_projects()
            selected_project = list_find(lambda p: str(p.project_id) == project_id_selected, projects)

            last_time_entries: List[TimeEntry] = self.user_service.get_last_ten_time_entries(user.user_id,
                                                                                             selected_project.project_id)
            if len(last_time_entries) == 0:
                return Message(
                    text="Can't find any time entries for *" + selected_project.name + "* :face_with_rolling_eyes:",
                    response_type="ephemeral",
                    mrkdwn=True
                ).dump()

            actions = [
                Action(
                    name="time_entries_list",
                    text="Select time entry",
                    type=ActionType.SELECT.value,
                    options=[TextSelectOption(text=string_helper.make_option_time_string(te), value=te.time_entry_id)
                             for te in last_time_entries]
                ),
            ]
            attachments = [
                Attachment(
                    text="Select time entry to remove",
                    fallback="Select time entry",
                    color="#3AA3E3",
                    attachment_type="default",
                    callback_id=string_helper.get_full_class_name(DeleteTimeEntryPayload),
                    actions=actions
                )
            ]
            return Message(
                text="There are the last time entries for *" + selected_project.name + "*:",
                response_type="ephemeral",
                mrkdwn=True,
                attachments=attachments
            ).dump()

        elif action_name == 'time_entries_list':
            # time entry selected
            time_entry_id_selected = action.selected_options[0].value
            time_entry: TimeEntry = self.user_service.get_time_entry(user.user_id, time_entry_id_selected)

            actions = [
                Action(name="remove", text="Remove", style="danger", type=ActionType.BUTTON.value,
                       value=str(time_entry.time_entry_id)),
                Action(name="cancel", text="Cancel", type=ActionType.BUTTON.value, value="remove")
            ]
            attachments = [
                Attachment(
                    text="Click 'Remove' to confirm:",
                    color="#3AA3E3", attachment_type="default",
                    callback_id=string_helper.get_full_class_name(DeleteTimeEntryPayload),
                    actions=actions)
            ]
            return Message(
                text="Time entry will be removed...",
                response_type="ephemeral",
                mrkdwn=True,
                attachments=attachments
            ).dump()
        elif action_name == 'remove':
            # confirmation
            self.user_service.delete_time_entry(user.user_id, int(action.value))

            return Message(
                text="Time entry removed! :wink:",
                response_type="ephemeral",
            ).dump()

        elif action_name == 'cancel':
            # cancellation
            return Message(
                text="Canceled :wink:",
                response_type="ephemeral",
            ).dump()

        else:
            logging.error("Unsupported action name: {0}".format(action_name))
            raise NotImplementedError()

    def create_dialog(self, command_body, argument, action) -> Dialog:
        raise NotImplementedError()

    def select_project(self, command_body, argument, action):

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
                callback_id=string_helper.get_full_class_name(DeleteTimeEntryPayload),
                actions=actions
            )
        ]
        return Message(
            text="I'm going to remove time entry :wastebasket:...",
            response_type="ephemeral",
            attachments=attachments
        ).dump()

    def get_projects_option_list_as_text(self, user_id=None) -> List[TextSelectOption]:
        projects = self.project_service.get_projects_by_user(user_id) if user_id else self.project_service.get_projects()
        return [TextSelectOption(p.name, p.project_id) for p in projects]
