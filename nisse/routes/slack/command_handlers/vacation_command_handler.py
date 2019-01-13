import logging
from datetime import datetime, timedelta

from flask.config import Config
from flask_injector import inject
from marshmallow import ValidationError
from slackclient import SlackClient

from nisse.models.slack.dialog import Element, Dialog
from nisse.models.slack.payload import RequestFreeDaysPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services import GoogleCalendarService
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.services.vacation_service import VacationService
from nisse.utils import string_helper
from nisse.utils.date_helper import parse_formatted_datetime


class VacationCommandHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
        slack_client: SlackClient, project_service: ProjectService, 
        reminder_service: ReminderService, vacation_service: VacationService,
        calendar_service: GoogleCalendarService
        ):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)
        self.vacation_service = vacation_service
        self.calendar_service = calendar_service

    def handle(self, payload: RequestFreeDaysPayload):
        start_date = parse_formatted_datetime(payload.submission.start_date)
        end_date = parse_formatted_datetime(payload.submission.end_date)
        user = self.get_user_by_slack_user_id(payload.user.id)

        if start_date <= self.current_date():
            raise ValidationError(
                'Vacation must start in the future', ['start_date'])

        if end_date < start_date:
            raise ValidationError(
                'End date must not be lower than start date', ['end_date'])

        user_vacatios = self.vacation_service.get_user_vacations_since(
            user.user_id, self.current_date())
        for vacation in user_vacatios:
            if vacation.start_date <= start_date and start_date <= vacation.end_date:
                raise ValidationError('Vacation must not start within other vacation. Conflicting vacation: {0} to {1}'.format(vacation.start_date.date(), vacation.end_date.date()), ['start_date'])
            if vacation.start_date <= end_date and end_date <= vacation.end_date:
                raise ValidationError('Vacation must not end within other vacation. Conflicting vacation: {0} to {1}'.format(vacation.start_date.date(), vacation.end_date.date()), ['end_date'])

        self.vacation_service.insert_user_vacation(user.user_id, start_date, end_date, payload.submission.reason)
        self.calendar_service.report_free_day("{0} {1}".format(user.first_name, user.last_name), user.username, start_date, end_date, payload.submission.reason)
        self.send_message_to_client(payload.user.id, "Reported vacation from `{0}` to `{1}`. Reason: `{2}`".format(start_date.strftime("%A, %d %B"), end_date.strftime("%A, %d %B"), payload.submission.reason))

    def create_dialog(self, command_body, argument, action) -> Dialog:
        tomorrow_date = datetime.now().date() + timedelta(days=1)

        elements = [
            Element("Start day", "text", "start_date", "specify date", tomorrow_date),
            Element("End day", "text", "end_date", "specify date"),
            Element("Reason", "textarea", "reason", "Reason", optional='true')
        ]
        return Dialog("Submit free days", "Submit", string_helper.get_full_class_name(RequestFreeDaysPayload), elements)
