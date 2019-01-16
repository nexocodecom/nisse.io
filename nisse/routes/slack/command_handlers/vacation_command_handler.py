import logging
from datetime import datetime, timedelta
from typing import List

from flask.config import Config
from flask_injector import inject
from marshmallow import ValidationError
from slackclient import SlackClient

from nisse.models.database import Vacation
from nisse.models.slack.common import ActionType
from nisse.models.slack.dialog import Element, Dialog
from nisse.models.slack.message import Action, Attachment, Message, TextSelectOption
from nisse.models.slack.payload import RequestFreeDaysPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services import GoogleCalendarService
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.services.vacation_service import VacationService
from nisse.utils import string_helper
from nisse.utils.date_helper import parse_formatted_date


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

        user = self.get_user_by_slack_user_id(payload.user.id)

        if payload.submission:
            # handle add vacation - dialog submission
            start_date = parse_formatted_date(payload.submission.start_date)
            end_date = parse_formatted_date(payload.submission.end_date)

            self.validate_new_vacation(start_date, end_date, user)

            result = self.calendar_service.report_free_day("{0} {1}".format(user.first_name, user.last_name),
                                                           user.username, start_date, end_date)
            self.vacation_service.insert_user_vacation(user.user_id, start_date, end_date, result["id"])
            self.send_message_to_client(payload.user.id,
                                        "Reported vacation from `{0}` to `{1}`".format(start_date.strftime("%A, %d %B"),
                                                                                       end_date.strftime("%A, %d %B")))
        else:
            action_name = next(iter(payload.actions))
            if action_name == 'vacation_list':
                # confirmation
                vacation_id = payload.actions[action_name].selected_options[0].value
                return VacationCommandHandler.create_vacation_selected_message(vacation_id).dump()
            elif action_name == 'remove':

                # handle delete vacation
                vacation_id = payload.actions[action_name].value
                vacation: Vacation = self.vacation_service.get_vacation_by_id(user.user_id, vacation_id)

                self.calendar_service.delete_free_day(vacation.event_id)
                self.vacation_service.delete_vacation(user.user_id, vacation.vacation_id)

                return Message(text="Vacation removed! :wink:", response_type="ephemeral").dump()

            elif action_name == 'cancel':
                # cancellation
                return Message(text="Canceled :wink:", response_type="ephemeral").dump()
            else:
                logging.error("Unsupported action name: {0}".format(action_name))
                raise NotImplementedError()


    def validate_new_vacation(self, start_date, end_date, user):

        if start_date <= self.current_date().date():
            raise ValidationError(
                'Vacation must start in the future', ['start_date'])

        if end_date < start_date:
            raise ValidationError(
                'End date must not be lower than start date', ['end_date'])

        user_vacations = self.vacation_service.get_user_vacations_since(
            user.user_id, self.current_date())

        for vacation in user_vacations:
            if vacation.start_date <= start_date <= vacation.end_date:
                raise ValidationError('Vacation must not start within other vacation. Conflicting vacation: {0} to {1}'
                                      .format(vacation.start_date, vacation.end_date), ['start_date'])
            if vacation.start_date <= end_date <= vacation.end_date:
                raise ValidationError('Vacation must not end within other vacation. Conflicting vacation: {0} to {1}'
                                      .format(vacation.start_date, vacation.end_date), ['end_date'])

    def create_dialog(self, command_body, argument, action) -> Dialog:
        tomorrow_date = datetime.now().date() + timedelta(days=1)

        elements = [
            Element("Start day", "text", "start_date", "specify date", tomorrow_date),
            Element("End day", "text", "end_date", "specify date", tomorrow_date)
        ]
        return Dialog("Submit free days", "Submit", string_helper.get_full_class_name(RequestFreeDaysPayload), elements)

    @staticmethod
    def create_vacation_selected_message(vacation_id):
        actions = [
            Action(name="remove", text="Remove", style="danger", type=ActionType.BUTTON.value,
                   value=str(vacation_id)),
            Action(name="cancel", text="Cancel", type=ActionType.BUTTON.value, value="remove")
        ]
        attachments = [
            Attachment(
                text="Click 'Remove' to confirm:",
                color="#3AA3E3", attachment_type="default",
                callback_id=string_helper.get_full_class_name(RequestFreeDaysPayload),
                actions=actions)
        ]
        return Message(
            text="Vacation will be removed...",
            response_type="ephemeral",
            mrkdwn=True,
            attachments=attachments
        )

    def select_vacation_to_remove(self, command_body, argument, action):

        user = self.get_user_by_slack_user_id(command_body['user_id'])

        user_vacations: List[Vacation] = self.vacation_service.get_ten_newest_user_vacations(user.user_id)

        if not user_vacations:
            return Message(
                text="There is nothing to delete... ",
                response_type="ephemeral",
                mrkdwn=True
            ).dump()

        actions = [
            Action(
                name="vacation_list",
                text="Select vacation to delete",
                type=ActionType.SELECT.value,
                options=[TextSelectOption(text=string_helper.make_option_vacations_string(vac), value=vac.vacation_id)
                         for vac in user_vacations]
            ),
        ]
        attachments = [
            Attachment(
                text="Select vacation to delete",
                fallback="Select vacation to delete",
                color="#3AA3E3",
                attachment_type="default",
                callback_id=string_helper.get_full_class_name(RequestFreeDaysPayload),
                actions=actions
            )
        ]
        return Message(
            text="I'm going to remove some vacations :wastebasket:...",
            response_type="ephemeral",
            mrkdwn=True,
            attachments=attachments
        ).dump()

    def dispatch_vacation(self, command_body, arguments, action):
        if not arguments:
            return self.show_dialog(command_body, arguments, action)
        if arguments[0] == "delete" or arguments[0] == "del":
            return self.select_vacation_to_remove(command_body, arguments, action)