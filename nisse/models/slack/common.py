from enum import Enum

from marshmallow import Schema, fields, post_load


class LabelSelectOption(object):

    class Schema(Schema):
        label = fields.String()
        value = fields.String()

        @post_load
        def make_obj(self, data):
            return LabelSelectOption(**data)

    def __init__(self, label, value):
        self.label = label
        self.value = value


class Option(object):

    class Schema(Schema):
        value = fields.String()

        @post_load
        def make_obj(self, data):
            return Option(**data)

    def __init__(self, value):
        self.value = value


class ActionType(Enum):
    SELECT = 'select'
    TEXT = 'text'
    TEXT_AREA = 'textarea'
    BUTTON = "button"
