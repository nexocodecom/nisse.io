import json
from flask import Flask, jsonify
from flask import request
from flask_injector import inject
from flask_restful import Resource
from marshmallow import ValidationError, UnmarshalResult

from nisse.models.slack.errors import Error, ErrorSchema
from nisse.models.slack.payload import Payload, GenericPayloadSchema
from nisse.services.slack.slack_command_service import SlackCommandService


class SlackDialogSubmission(Resource):

    @inject
    def __init__(self, app: Flask, slack_command_service: SlackCommandService):
        self.app = app
        self.slack_command_service = slack_command_service
        self.schema = GenericPayloadSchema()

    def post(self):

        result: UnmarshalResult = self.schema.load(json.loads(request.form["payload"]))
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
            result = payload.handle(self.slack_command_service)
            return (result, 200) if result else (None, 204)
