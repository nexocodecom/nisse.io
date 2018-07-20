from flask import Flask
from flask import request
from flask_injector import inject
from flask_restful import Resource

from nisse.services.slack.slack_command_service import SlackCommandService


class SlackCommand(Resource):

    @inject
    def __init__(self, app: Flask, slack_command_service: SlackCommandService):
        self.app = app
        self.slack_command_service = slack_command_service

    def post(self):
        command_body = request.form

        # Verify that the request came from Slack
        if self.app.config['SLACK_VERIFICATION_TOKEN'] != command_body["token"]:
            self.app.logger.error("Error: invalid verification token!"
                                  " Received {} but was expecting {}"
                                  .format(command_body["token"], self.app.config['SLACK_VERIFICATION_TOKEN']))
            return "Request contains invalid Slack verification token", 403

        command_first_param = next(iter(command_body["text"].split(" ") or []), None)

        return {
            None: self.tt,
            "": self.tt,
            'list': self.tt,
            'report': self.tt,
            'delete': self.tt,
            'reminder': self.reminder
            }.get(command_first_param, self.tt)(command_body, command_first_param)

    def tt(self, command_body, command_param):
        params = iter(command_body["text"].split(" ") or [])
        next(params, None)
        command_inner_param = next(params, None)
        if command_param is None or command_param == "":
            return self.slack_command_service.submit_time_dialog(command_body)
        if command_param == "list":
            return self.slack_command_service.list_command_message(command_body, command_inner_param)
        if command_param == "report":
            return self.slack_command_service.report_dialog(command_body)
        if command_param == "delete":
            return self.slack_command_service.delete_command_message(command_body)
        if command_param == "help":
            return self.slack_command_service.help_command_message(command_body)

        return None, 204

    def reminder(self, command_body, param):
        params = iter(command_body["text"].split(" ") or [])
        next(params, None)
        command_param = next(params, None)
        if command_param is None or command_param == "":
            return self.slack_command_service.reminder_show(command_body)
        if command_param == "show":
            return self.slack_command_service.reminder_show(command_body)
        if command_param == "set":
            return self.slack_command_service.reminder_set(command_body)

        return None, 204
