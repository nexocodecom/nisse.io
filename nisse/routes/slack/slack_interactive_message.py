import json
from flask import Flask
from flask import request
from flask_injector import inject
from flask_restful import Resource
import nisse.services.slack.slack_command_service
from nisse.services.slack.slack_command_service import SlackCommandService


class SlackDialogSubmission(Resource):

    @inject
    def __init__(self, app: Flask, slack_command_service: SlackCommandService):
        self.app = app
        self.slack_command_service = slack_command_service

    def post(self):
        dialog_submission_body = json.loads(request.form["payload"])
        callback_id = dialog_submission_body.get("callback_id")

        if callback_id == nisse.services.slack.slack_command_service.CALLBACK_TOKEN_TIME_SUBMIT:
            return self.slack_command_service.save_submitted_time(dialog_submission_body)
        if callback_id == nisse.services.slack.slack_command_service.CALLBACK_TOKEN_LIST_COMMAND_TIME_RANGE:
            return self.slack_command_service.list_command_time_range_selected(dialog_submission_body)
        if callback_id == nisse.services.slack.slack_command_service.CALLBACK_TOKEN_DELETE_COMMAND_PROJECT:
            return self.slack_command_service.delete_command_project_selected(dialog_submission_body)
        if callback_id == nisse.services.slack.slack_command_service.CALLBACK_TOKEN_DELETE_COMMAND_TIME_ENTRY:
            return self.slack_command_service.delete_command_time_entry_selected(dialog_submission_body)
        if callback_id == nisse.services.slack.slack_command_service.CALLBACK_TOKEN_DELETE_COMMAND_CONFIRM:
            return self.slack_command_service.delete_command_time_entry_confirm_remove(dialog_submission_body)
        if callback_id == nisse.services.slack.slack_command_service.CALLBACK_TOKEN_REPORT_SUBMIT:
            return self.slack_command_service.report_generate_command(dialog_submission_body)
        if callback_id == nisse.services.slack.slack_command_service.CALLBACK_TOKEN_REMINDER_REPORT_BTN:
            return self.slack_command_service.submit_time_dialog_reminder(dialog_submission_body)

        return None, 204
