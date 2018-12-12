import unittest
from marshmallow import pprint
from flask import jsonify
from nisse.models.slack.errors import Error, ErrorSchema


class ErrorsTests(unittest.TestCase):

    def test_errors_marshalling(self):
        errors = [Error(name="Test Name 1", error="Unknown Test Error 1"),
                  Error(name="Test Name 2", error="Unknown Test Error 2")]
        schema = ErrorSchema(many=True)
        result = schema.dump(errors).data

        expectedResult = [{'error': 'Unknown Test Error 1', 'name': 'Test Name 1'}, {'error': 'Unknown Test Error 2', 'name': 'Test Name 2'}]
        self.assertEqual(result, expectedResult)
