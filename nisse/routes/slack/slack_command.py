from flask import Flask, jsonify
from flask import request
from flask_injector import inject
from flask_restful import Resource
from marshmallow import ValidationError
from typing import Dict

from nisse.models.slack.errors import ErrorSchema, Error
from nisse.models.slack.message import Message
from nisse.services.exception import DataException, SlackUserException
from nisse.routes.slack.command_handlers.vacation_command_handler import VacationCommandHandler
from nisse.services.slack.slack_command_service import SlackCommandService



class SlackCommand(Resource):

    @inject
    def __init__(self, app: Flask, slack_command_service: SlackCommandService, vacationCommandHandler: VacationCommandHandler):
        self.app = app
        self.slack_command_service = slack_command_service
        self.error_schema = ErrorSchema()
        self.dispatcher = {
            None: self.slack_command_service.submit_time_dialog,
            "": self.slack_command_service.submit_time_dialog,
            'list': self.slack_command_service.list_command_message,
            'report': self.slack_command_service.report_pre_dialog,
            'delete': self.slack_command_service.delete_command_message,
            'vacation': vacationCommandHandler.show_dialog,
            'reminder': self.reminder,
            'help': self.slack_command_service.help_command_message
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

    def reminder(self, command_body, arguments, action):
        if not arguments or arguments[0] == "show":
            return self.slack_command_service.reminder_show(command_body, arguments, action)
        if arguments[0] == "set":
            return self.slack_command_service.reminder_set(command_body, arguments, action)

    @staticmethod
    def handle_other(commands_body, arguments, action):
        return Message(
            text="Oops, I don't understand *" + action + "* :thinking_face:",
            response_type="ephemeral",
            mrkdwn=True
        ).dump()
