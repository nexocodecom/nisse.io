from nisse.models import TimeEntry
from nisse.models.slack.common import ActionType
from nisse.models.slack.message import Attachment, Message, Action, TextSelectOption
from nisse.models.slack.payload import DeleteCommandPayload, DeleteTimeEntryPayload, DeleteConfirmPayload
from nisse.utils import string_helper


def create_select_project_model(project_options_list, user_default_project_id):
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
    return Message(
        text="I'm going to remove time entry :wastebasket:...",
        response_type="ephemeral",
        attachments=attachments
    )


def create_select_time_entry_model(last_time_entries, selected_project):
    actions = [
        Action(
            name="time_entries_list",
            text="Select time entry",
            type=ActionType.SELECT.value,
            options=[TextSelectOption(text=string_helper.make_option_time_string(te), value=te.time_entry_id) for te in last_time_entries]
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
    )


def create_delete_time_entry_model(time_entry: TimeEntry):
    actions = [
        Action(name="remove", text="Remove", style="danger", type=ActionType.BUTTON.value, value=str(time_entry.time_entry_id)),
        Action(name="cancel", text="Cancel", type=ActionType.BUTTON.value, value="remove")
    ]
    attachments = [
        Attachment(
            text="Click 'Remove' to confirm:",
            color="#3AA3E3", attachment_type="default",
            callback_id=string_helper.get_full_class_name(DeleteConfirmPayload),
            actions=actions)
    ]
    return Message(
        text="Time entry will be removed...",
        response_type="ephemeral",
        mrkdwn=True,
        attachments=attachments
    )


def create_delete_successful_message():
    return Message(
        text="Time entry removed! :wink:",
        response_type="ephemeral",
    )


def create_delete_cancel_message():
    Message(
        text="Canceled :wink:",
        response_type="ephemeral",
    )


def create_delete_not_found_message(project_name: str):
    return Message(
        text="Can't find any time entries for *" + project_name + "* :face_with_rolling_eyes:",
        response_type="ephemeral",
        mrkdwn=True
    )