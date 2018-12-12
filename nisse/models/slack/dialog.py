from marshmallow import Schema, fields, post_load
from typing import List, Dict

from nisse.models.slack.common import SelectOptionSchema, LabelSelectOption


class Dialog(object):

    def __init__(self, title, submit_label, callback_id, elements):
        self.title = title
        self.submit_label = submit_label
        self.callback_id = callback_id
        self.elements = elements

    def dump(self) -> Dict:
        return DialogSchema().dump(self).data


class Element(object):

    def __init__(self, label, type, name, placeholder=None, value=None, subtype=None, hint=None, options: List[LabelSelectOption] = None, optional=None):
        self.label = label
        self.type = type
        self.name = name
        if placeholder:
            self.placeholder = placeholder
        if value:
            self.value = value
        if subtype:
            self.subtype = subtype
        if hint:
            self.hint = hint
        if options:
            self.options = options
        if optional:
            self.optional = optional


class ElementSchema(Schema):
    label = fields.String()
    type = fields.String()
    name = fields.String()
    placeholder = fields.String(missing=True)
    value = fields.String(missing=True)
    subtype = fields.String(missing=True)
    hint = fields.String(missing=True)
    optional = fields.String(missing=True)
    options = fields.List(fields.Nested(SelectOptionSchema), missing=True)

    @post_load
    def make_obj(self, data):
        return Element(**data)


class DialogSchema(Schema):
    title = fields.String()
    submit_label = fields.String()
    callback_id = fields.String()
    elements = fields.List(fields.Nested(ElementSchema))

    @post_load
    def make_obj(self, data):
        return Dialog(**data)
