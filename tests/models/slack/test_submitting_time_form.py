import unittest
from marshmallow import pprint, fields, Schema
from flask import jsonify
from nisse.models.slack.errors import Error, ErrorSchema
from nisse.models.slack.payload import Team, SlackUser, Channel, TimeReportingForm, Payload, PayloadSchema


class ErrorsTests(unittest.TestCase):

    def test_form_unmarshalling(self):
        # payload = "{'type':'dialog_submission','token':'3opqSJ43GY7mqlfHedOYschu','action_ts':'1532687081.979292','team':{'id':'TB32PEP2B','domain':'witalinc'},'user':{'id':'UBXJV8HFF','name':'radoslaw.kaminski'},'channel':{'id':'DBWP5D49W','name':'directmessage'},'submission':{'project':'2','day':'2018-07-27','duration':'4','comment':'4'},'callback_id':'tt-dialog-time-sbt','response_url':'test'}"
        payload = {'type':'abc','token':'abc','action_ts':'abc','team':{'id':'abc','domain':'abc'},'user':{'id':'abc','name':'abc'},'channel':{'id':'abc','name':'abc'},'submission':{'project':'abc','day':'abc','duration':'abc','comment':'abc'},'callback_id':'abc','response_url':'abc'}
        # payload = "{}"
        schema = PayloadSchema()
        form = schema.load(payload)
        print(form)

    def test_form_marshalling(self):
        team = Team("TB32", "witalinc")
        user = SlackUser("UBXJ", "radoslaw.kaminski")
        channel = Channel("DBWP", "directmessage")        
        form = Payload("dialog_submission", "3opq", "123.45", team, user, channel, "http://", None, "trigger_id", "messages_ts")
        schema = PayloadSchema()
        result = schema.dump(form)
        print(result)
        pay: Payload = schema.load(result.data)        
        print(pay.data['trigger_id'])



