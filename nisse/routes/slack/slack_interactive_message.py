import json
from flask import Flask, jsonify
from flask import request
from flask_injector import inject
from flask_restful import Resource
from marshmallow import ValidationError, UnmarshalResult

from injector import Injector
from nisse.models.slack.errors import Error, ErrorSchema
from nisse.models.slack.payload import Payload, GenericPayloadSchema, DeleteConfirmPayload
from nisse.services.slack.slack_command_service import SlackCommandService
from nisse.routes.slack.command_handlers import SlackCommandHandler
from nisse.utils import string_helper


class SlackDialogSubmission(Resource):

    @inject
    def __init__(self, app: Flask, slack_command_service: SlackCommandService, injector: Injector):
        self.app = app
        self.slack_command_service = slack_command_service
        self.schema = GenericPayloadSchema()
        self.injector = injector

    def post(self):

        result: UnmarshalResult = self.schema.load(
            json.loads(request.form["payload"]))
        if result.errors and result.errors['submission']:
            submission = result.errors['submission']
            errors = []
            for i, field in enumerate(submission):
                errors.append(Error(field, submission[field]))

            schema = ErrorSchema(many=True)
            result = schema.dump(errors).data
            return jsonify({'errors': result})

        else:
            payload: Payload = result.data
            if payload.handler_type is not None:
                return self.try_use_handler(payload)
            else:
                result = payload.handle(self.slack_command_service)
            return (result, 200) if result else (None, 204)

    def try_use_handler(self, payload: Payload):
        handler: SlackCommandHandler = self.injector.get(payload.handler_type())
        result = handler.handle(payload)
        return (result, 200) if result else (None, 204)
