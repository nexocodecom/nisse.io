import logging
from datetime import date
from decimal import Decimal
from typing import List

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.DTO import TimeRecordDto
from nisse.models.slack.common import LabelSelectOption
from nisse.models.slack.dialog import Element, Dialog
from nisse.models.slack.message import Attachment
from nisse.models.slack.payload import TimeReportingFormPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.utils import string_helper
from nisse.utils.date_helper import get_float_duration
from nisse.utils.validation_helper import list_find

DAILY_HOUR_LIMIT = 20


class SubmitTimeCommandHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService):
        super().__init__(config, logger, user_service,
                         slack_client, project_service, reminder_service)

    def handle(self, payload: TimeReportingFormPayload):

        time_record = TimeRecordDto(
            day=payload.submission.day,
            hours=int(payload.submission.hours),
            minutes=int(payload.submission.minutes),
            comment=payload.submission.comment,
            project=payload.submission.project,
            user_id=payload.user.id
        )

        self.save_submitted_time_task(time_record)

    def create_dialog(self, command_body, argument, action) -> Dialog:
        slack_user_id = command_body['user_id']
        report_date = self.current_date().strftime("%Y-%m-%d") if(isinstance(action, str) or action is None) else action.value

        slack_user_details = self.user_service.get_user_by_slack_id(
            slack_user_id)

        project_options_list: List[LabelSelectOption] = self.get_projects_option_list_as_label(
            slack_user_details.user_id)
        user_default_project_id: str = self.get_default_project_id(
            project_options_list[0].value, slack_user_details)

        elements = [
            Element("Project", "select", "project", "Select a project", user_default_project_id, None, None,
                    project_options_list),
            Element("Day", "text", "day", "Specify date", report_date),
            Element("Duration hours", "select", "hours", None, "8", None,
                    None, SubmitTimeCommandHandler.get_duration_hours()),
            Element("Duration minutes", "select", "minutes", None, "0",
                    None, None, SubmitTimeCommandHandler.get_duration_minutes()),
            Element("Note", "textarea", "comment", None,
                    None, None, "Provide short description")
        ]
        return Dialog("Submitting time", "Submit", string_helper.get_full_class_name(TimeReportingFormPayload),
                      elements)

    @staticmethod
    def get_duration_hours():
        return [LabelSelectOption(n, n) for n in range(1, 13)]

    @staticmethod
    def get_duration_minutes() -> List[LabelSelectOption]:
        return [LabelSelectOption(n, n) for n in range(0, 60, 15)]

    def save_submitted_time_task(self, time_record: TimeRecordDto):

        user = self.get_user_by_slack_user_id(time_record.user_id)

        im_channel = self.slack_client.api_call(
            "im.open", user=time_record.user_id)

        if not im_channel["ok"]:
            self.logger.error("Can't open im channel for: " +
                              str(time_record.user_id) + '. ' + im_channel["error"])
            return

        # todo cache projects globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(
            p.project_id) == time_record.project, projects)

        if selected_project is None:
            self.logger.error("Project doesn't exist: " + time_record.project)
            return

        if list_find(lambda p: str(p.project_id) == time_record.project, user.user_projects) is None:
            self.project_service.assign_user_to_project(
                project=selected_project, user=user)

            # check if submitted hours doesn't exceed the limit
        submitted_time_entries = self.user_service.get_user_time_entries(user.user_id, time_record.get_parsed_date(),
                                                                         time_record.get_parsed_date())
        duration_float: float = get_float_duration(
            time_record.hours, time_record.minutes)
        if sum([te.duration for te in submitted_time_entries]) + Decimal(duration_float) > DAILY_HOUR_LIMIT:
            self.slack_client.api_call(
                "chat.postMessage",
                channel=im_channel['channel']['id'],
                text="Sorry, but You can't submit more than " +
                str(DAILY_HOUR_LIMIT) + " hours for one day.",
                as_user=True
            )
            return

        self.project_service.report_user_time(selected_project, user, duration_float, time_record.comment,
                                              time_record.get_parsed_date())

        attachments = [Attachment(
            title='Submitted ' + string_helper.format_duration_decimal(Decimal(duration_float)) + ' hour(s) for ' +
                  (
                      'Today' if time_record.day == date.today().isoformat() else time_record.day) + ' in ' + selected_project.name,
            text="_" + time_record.comment + "_",
            mrkdwn_in=["text", "footer"],
            footer=self.config['MESSAGE_SUBMIT_TIME_TIP']
        ).dump()]

        resp = self.slack_client.api_call(
            "chat.postMessage",
            channel=im_channel['channel']['id'],
            attachments=attachments,
            as_user=True
        )

        if not resp["ok"]:
            self.logger.error("Can't post message: " + resp.get("error"))
