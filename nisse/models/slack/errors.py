from marshmallow import Schema, fields


class Error(object):

    class Schema(Schema):
        name = fields.Str()
        error = fields.Str()

    def __init__(self, name, error):
        self.name = name
        self.error = error
