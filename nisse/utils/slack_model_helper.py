from typing import List

from nisse.models import TimeEntry
from nisse.models.slack.common import ActionType, LabelSelectOption
from nisse.models.slack.dialog import Element, Dialog
from nisse.models.slack.message import Attachment, Message, Action, TextSelectOption
from nisse.models.slack.payload import ListCommandPayload, TimeReportingFormPayload, ReportGenerateFormPayload, ReportGenerateDialogPayload, DeleteCommandPayload, DeleteTimeEntryPayload, DeleteConfirmPayload
from nisse.utils import string_helper
from nisse.utils.date_helper import TimeRanges
from flask import current_app

def create_help_command_message(command_body) -> Message:
    command_name = command_body["command"]

    attachments = [
        Attachment(
            text="*{0}* _(without any arguments)_: Submit working time".format(command_name),
            attachment_type="default",
            mrkdwn_in=["text"]
        ),
        Attachment(
            text="*{0} list*: See reported time".format(command_name),
            attachment_type="default",
            mrkdwn_in=["text"]
        ),
        Attachment(
            text="*{0} delete*: Remove reported time".format(command_name),
            attachment_type="default",
            mrkdwn_in=["text"]
        ),
        Attachment(
            text="*{0} reminder*: See reminder settings".format(command_name),
            attachment_type="default",
            mrkdwn_in=["text"]
        ),
        Attachment(
            text="*{0} report*: Generate report file".format(command_name),
            attachment_type="default",
            mrkdwn_in=["text"]
        ),
        Attachment(
            text='*{0} vacation*: Submit free time within range'.format(command_name),
            attachment_type="default",
            mrkdwn_in=['text']
        ),
        Attachment(
            text="*{0} reminder set [_mon:HH:MM,tue:HH:MM..._]*: Configure reminder time for particular day, or several days at once".format(command_name),
            attachment_type="default",
            mrkdwn_in=["text"]
        )
    ]

    return Message(
        text="*Nisse* is used for reporting working time. Following commands are available:",
        mrkdwn=True,
        response_type="default",
        attachments=attachments
    )

def create_select_period_for_reporting_model(command_body, inner_user_id, message_text):
    actions = [
        Action(
            name=inner_user_id if inner_user_id is not None else command_body['user_id'],
            text="Select time range...",
            type=ActionType.SELECT.value,
            options=[TextSelectOption(text=tr.value, value=tr.value) for tr in TimeRanges]
        )
    ]
    attachments = [
        Attachment(
            text="Generate report for",
            fallback="Select time range to report",
            color="#3AA3E3",
            attachment_type="default",
            callback_id=string_helper.get_full_class_name(ReportGenerateDialogPayload),
            actions=actions
        )
    ]

    return Message(
        text=message_text,
        response_type="ephemeral",
        mrkdwn=True,
        attachments=attachments
    )

def create_generate_report_dialog_model(previous_week, project_options_list, today):
    elements: Element = [
        Element(label="Date from", type="text", name='day_from', placeholder="Specify date", value=previous_week),
        Element(label="Date to", type="text", name='day_to', placeholder="Specify date", value=today),
        Element(label="Project", type="select", name='project', optional='true', placeholder="Select a project", options=project_options_list)
    ]

    return Dialog(title="Generate report", submit_label="Generate", callback_id=string_helper.get_full_class_name(ReportGenerateFormPayload), elements=elements)


def create_reminder_info_model(command_name, day_configuration):
    attachments = [
        Attachment(
            text=day_time,
            color="#D72B3F" if "OFF" in day_time else "#3AA3E3",
            attachment_type="default",
            mrkdwn_in=["text"]
        ) for day_time in day_configuration
    ]
    attachments.append(
        Attachment(
            text="",
            footer= current_app.config['MESSAGE_REMINDER_SET_TIP'].format(command_name),
            mrkdwn_in=["text", "footer"]
        )
    )
    return Message(
        text="Your reminder time is as follow:",
        response_type="ephemeral",
        mrkdwn=True,
        attachments=attachments
    )


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