from marshmallow import Schema, fields


class Error(object):
    def __init__(self, name, error):
        self.name = name
        self.error = error


class ErrorSchema(Schema):
    name = fields.Str()
    error = fields.Str()