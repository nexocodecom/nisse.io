from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.user_service import UserService
from nisse.services.project_service import Project, ProjectService
from nisse.services.day_off_service import Dayoff, DayOffService
from nisse.services.reminder_service import ReminderService
from nisse.models.slack.dialog import Element, Dialog
from slackclient import SlackClient
from nisse.utils import string_helper
import logging
from nisse.models.slack.payload import RequestFreeDaysPayload
from flask_injector import inject
from nisse.utils.date_helper import parse_formatted_datetime
from datetime import datetime
from marshmallow import ValidationError


class DayOffCommandHandler(SlackCommandHandler):

    @inject
    def __init__(self, logger: logging.Logger, user_service: UserService, slack_client: SlackClient, project_service: ProjectService, reminder_service: ReminderService, dayoff_service: DayOffService):
        super().__init__(logger, user_service, slack_client, project_service, reminder_service)
        self.dayoff_service = dayoff_service

    def handle(self, payload: RequestFreeDaysPayload):
        start_date = parse_formatted_datetime(payload.submission.start_date)
        end_date = parse_formatted_datetime(payload.submission.end_date)
        user = self.get_user_by_slack_user_id(payload.user.id)

        if start_date <= self.current_date():
            raise ValidationError(
                'Holiday must start in the future', ['start_date'])

        if end_date < start_date:
            raise ValidationError(
                'End date must not be lower than start date', ['end_date'])

        user_daysoff = self.dayoff_service.get_user_days_off_since(
            user.user_id, self.current_date())
        for dayoff in user_daysoff:
            if dayoff.start_date < start_date and start_date < dayoff.end_date:
                raise ValidationError('Day off must not start within other holiday', ['start_date'])
            if end_date < dayoff.end_date:
                raise ValidationError('Day off must not end within other holiday', ['end_date'])

        self.dayoff_service.insert_user_day_off(
            user.user_id, start_date, end_date, payload.submission.reason)

    def create_dialog(self, command_body, argument, action) -> Dialog:
        nowdate = datetime.now().date()

        elements = [
            Element("Start day", "text", "start_date", "specify date", nowdate),
            Element("End day", "text", "end_date", "specify date"),
            Element("Reason", "textarea", "reason", "Reason")
        ]
        return Dialog("Submit free days", "Submit", string_helper.get_full_class_name(RequestFreeDaysPayload), elements)
