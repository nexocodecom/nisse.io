import json
from itertools import zip_longest
from logging import Logger

from flask import Flask, jsonify
from flask import request
from flask_injector import inject
from flask_restful import Resource
from injector import Injector
from marshmallow import ValidationError, UnmarshalResult

from nisse.models.slack.errors import Error
from nisse.models.slack.payload import Payload, GenericPayloadSchema
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler


class SlackDialogSubmission(Resource):

    @inject
    def __init__(self, logger: Logger, app: Flask, injector: Injector):
        self.app = app
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

            schema = Error.Schema(many=True)
            result = schema.dump(errors).data
            return jsonify({'errors': result})

        else:
            payload: Payload = result.data

            try:
                if payload.handler_type() is not None:
                    handler: SlackCommandHandler = self.injector.get(payload.handler_type())
                    result = handler.handle(payload)
                    return (result, 200) if result else (None, 204)
                else:
                    raise ValueError('Unsupported payload_type: {0}'.format(payload))
            except ValidationError as e:
                errors = []
                for error, name in zip_longest(e.messages, e.field_names):
                    errors.append({"error": error, "name": name})
                return {"errors": errors}, 200
            except:
                self.logger.log(50, 'Fatal error: %s', exc_info=1)
                return 'Internal server error', 500


