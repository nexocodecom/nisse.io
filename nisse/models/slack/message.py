from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict
from marshmallow import Schema, fields, post_load


class TextSelectOption(object):

    def __init__(self, text, value):
        self.text = text
        self.value = value


class TextSelectOptionSchema(Schema):
    text = fields.String()
    value = fields.String()

    @post_load
    def make_obj(self, data):
        return TextSelectOption(**data)


@dataclass
class Action:
    name: str
    text: str
    type: str
    options: List[TextSelectOption] = None
    style: str = None
    value: str = None


class ActionSchema(Schema):
    name = fields.Str()
    text = fields.Str()
    type = fields.Str()
    options = fields.List(fields.Nested(TextSelectOptionSchema), allow_none=True)
    style = fields.Str(allow_none=True)
    value = fields.Str(allow_none=True)

    @post_load
    def make_obj(self, data):
        return Action(**data)


@dataclass
class Attachment:
    text: str
    title: str = None
    color: str = None
    attachment_type: str = None
    callback_id: str = None
    actions: List[Action] = None
    fallback: str = None
    mrkdwn_in: List[str] = None
    footer: str = None

    def dump(self) -> Dict:
        return AttachmentSchema().dump(self).data


class AttachmentSchema(Schema):
    text = fields.Str()
    title = fields.Str(allow_none=True)
    color = fields.Str(allow_none=True)
    attachment_type = fields.Str(allow_none=True)
    callback_id = fields.Str(allow_none=True)
    actions = fields.List(fields.Nested(ActionSchema), allow_none=True)
    fallback = fields.Str(allow_none=True)
    mrkdwn_in: fields.List(fields.Str(), allow_none=True)
    footer = fields.Str(allow_none=True)

    @post_load
    def make_obj(self, data):
        return Attachment(**data)


@dataclass
class Message:
    text: str
    response_type: str
    mrkdwn: bool = None
    attachments: List[Attachment] = None

    def dump(self) -> Dict:
        return MessageSchema().dump(self).data


class MessageSchema(Schema):
    text = fields.Str()
    response_type = fields.Str()
    mrkdwn = fields.Bool(allow_none=True)
    attachments = fields.List(fields.Nested(AttachmentSchema), allow_none=True)

    @post_load
    def make_obj(self, data):
        return Message(**data)
