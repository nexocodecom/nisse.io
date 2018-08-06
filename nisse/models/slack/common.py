from dataclasses import dataclass
from enum import Enum

from marshmallow import Schema, fields, post_load


class LabelSelectOption(object):

    def __init__(self, label, value):
        self.label = label
        self.value = value


class SelectOptionSchema(Schema):
    label = fields.String()
    value = fields.String()

    @post_load
    def make_obj(self, data):
        return LabelSelectOption(**data)


class Option(object):

    def __init__(self, value):
        self.value = value


class OptionSchema(Schema):
    value = fields.String()

    @post_load
    def make_obj(self, data):
        return Option(**data)


class ActionType(Enum):
    SELECT = 'select'
    TEXT = 'text'
    TEXT_AREA = 'textarea'
    BUTTON = "button"
