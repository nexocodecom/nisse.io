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
from logging import Logger


class SlackDialogSubmission(Resource):

    @inject
    def __init__(self, logger: Logger, app: Flask, slack_command_service: SlackCommandService, injector: Injector):
        self.app = app
        self.slack_command_service = slack_command_service
        self.schema = GenericPayloadSchema()
        self.injector = injector
        self.logger = logger

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

            #this one is for future refactor of slackcommandservice since it is growing bigger and bigger and will eventually turn into god class
            if payload.handler_type is not None:
                return self.try_use_handler(payload)
            else:
                result = payload.handle(self.slack_command_service)
            return (result, 200) if result else (None, 204)

    #for refactor purpose
    def try_use_handler(self, payload: Payload):
        try:
            handler: SlackCommandHandler = self.injector.get(
                payload.handler_type())
            result = handler.handle(payload)
            return (result, 200) if result else (None, 204)
        except ValidationError as e:
            errors = []
            if len(e.field_names) == len(e.messages):
                for idx, err in enumerate(e.messages):
                    errors.append({"error": err, "name": e.field_names[idx]})
                return ({"errors": errors}, 200)

            return ({"errors": e.messages}, 200)
        except:
            self.logger.log('Fatal', 'Fatal error: %s', exc_info=1)
            return ('Internal servier error', 500)
