from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict

from marshmallow import Schema, fields, post_load, post_dump


class TextSelectOption(object):

    class Schema(Schema):
        text = fields.String()
        value = fields.String()

        @post_load
        def make_obj(self, data):
            return TextSelectOption(**data)

    def __init__(self, text, value):
        self.text = text
        self.value = value


@dataclass
class Confirmation:

    class Schema(Schema):
        text = fields.Str()
        title = fields.Str(allow_none=True)
        ok_text = fields.Str(allow_none=True)
        dismiss_text = fields.Str(allow_none=True)

        @post_load
        def make_obj(self, data):
            return Confirmation(**data)

    text: str
    title: str
    ok_text: str
    dismiss_text: str


@dataclass
class Action:

    class Schema(Schema):
        name = fields.Str()
        text = fields.Str()
        type = fields.Str()
        options = fields.List(fields.Nested(TextSelectOption.Schema), allow_none=True)
        style = fields.Str(allow_none=True)
        value = fields.Str(allow_none=True)
        confirm = fields.Nested(Confirmation.Schema, allow_none=True)

        @post_load
        def make_obj(self, data):
            return Action(**data)

        @post_dump
        def clean_missing(self, data):
            ret = data.copy()
            for key in filter(lambda key: data[key] is None, data):
                del ret[key]
            return ret

    name: str
    text: str
    type: str
    options: List[TextSelectOption] = None
    style: str = None
    value: str = None
    confirm: Confirmation = None

    def dump(self) -> Dict:
        return Action.Schema().dump(self).data


@dataclass
class Attachment:

    class Schema(Schema):
        text = fields.Str()
        title = fields.Str(allow_none=True)
        color = fields.Str(allow_none=True)
        attachment_type = fields.Str(allow_none=True)
        callback_id = fields.Str(allow_none=True)
        actions = fields.List(fields.Nested(Action.Schema), allow_none=True)
        fallback = fields.Str(allow_none=True)
        mrkdwn_in: fields.List(fields.Str(), allow_none=True)
        footer = fields.Str(allow_none=True)

        @post_load
        def make_obj(self, data):
            return Attachment(**data)

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
        return Attachment.Schema().dump(self).data


@dataclass
class Message:

    class Schema(Schema):
        text = fields.Str()
        response_type = fields.Str()
        mrkdwn = fields.Bool(allow_none=True)
        attachments = fields.List(fields.Nested(Attachment.Schema), allow_none=True)

        @post_load
        def make_obj(self, data):
            return Message(**data)

    text: str
    response_type: str
    mrkdwn: bool = None
    attachments: List[Attachment] = None

    def dump(self) -> Dict:
        return Message.Schema().dump(self).data


