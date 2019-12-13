from typing import Dict

from flask import Flask
from flask import request
from flask_injector import inject
from flask_restful import Resource

from nisse.models.slack.errors import Error
from nisse.models.slack.message import Message
from nisse.routes.slack.command_handlers.delete_time_command_handler import DeleteTimeCommandHandler
from nisse.routes.slack.command_handlers.food_handler import FoodHandler
from nisse.routes.slack.command_handlers.list_command_handler import ListCommandHandler
from nisse.routes.slack.command_handlers.project_command_handler import ProjectCommandHandler
from nisse.routes.slack.command_handlers.reminder_command_handler import ReminderCommandHandler
from nisse.routes.slack.command_handlers.report_command_handler import ReportCommandHandler
from nisse.routes.slack.command_handlers.show_help_command_handler import ShowHelpCommandHandler
from nisse.routes.slack.command_handlers.submit_time_command_handler import SubmitTimeCommandHandler
from nisse.routes.slack.command_handlers.vacation_command_handler import VacationCommandHandler
from nisse.services.exception import DataException, SlackUserException


class SlackCommand(Resource):

    @inject
    def __init__(self, app: Flask,
                 vacation_command_handler: VacationCommandHandler,
                 submit_time_command_handler: SubmitTimeCommandHandler,
                 list_command_handler: ListCommandHandler,
                 set_reminder_handler: ReminderCommandHandler,
                 show_help_handler: ShowHelpCommandHandler,
                 report_command_handler: ReportCommandHandler,
                 delete_time_command_handler: DeleteTimeCommandHandler,
                 project_command_handler: ProjectCommandHandler,
                 food_handler: FoodHandler):
        self.app = app
        self.set_reminder_handler = set_reminder_handler
        self.error_schema = Error.Schema()
        self.dispatcher = {
            None: submit_time_command_handler.show_dialog,
            "": submit_time_command_handler.show_dialog,
            'list': list_command_handler.list_command_message,
            'report': report_command_handler.report_pre_dialog,
            'delete': delete_time_command_handler.select_project,
            'vacation': vacation_command_handler.dispatch_vacation,
            'reminder': set_reminder_handler.dispatch_reminder,
            'project': project_command_handler.dispatch_project_command,
            'order':food_handler.order_start,
            'checkout':food_handler.order_checkout,
            'pay':food_handler.show_debt,
            'help': show_help_handler.create_help_command_message
        }

    def post(self):
        command_body = request.form

        # Verify that the request came from Slack
        if self.app.config['SLACK_VERIFICATION_TOKEN'] != command_body["token"]:
            self.app.logger.error("Error: invalid verification token!"
                                  " Received {} but was expecting {}"
                                  .format(command_body["token"], self.app.config['SLACK_VERIFICATION_TOKEN']))
            return "Request contains invalid Slack verification token", 403

        params = command_body["text"].split(" ") or []
        action = params[0]
        arguments = params[1:]

        try:
            callback = self.dispatcher.get(action, self.handle_other)
            result = callback(command_body, arguments, action)
            return (result, 200) if result else (None, 204)

        except DataException as e:
            error_result: Dict = self.error_schema.dump(
                {'errors': [Error(name=e.field, error=e.message)]}).data
            return error_result, 200
        except SlackUserException as e:
            return Message(text=e.message, response_type="ephemeral").dump(), 200

    @staticmethod
    def handle_other(commands_body, arguments, action):
        return Message(
            text="Oops, I don't understand *" + action + "* command :thinking_face:",
            response_type="ephemeral",
            mrkdwn=True
        ).dump()
