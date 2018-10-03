from datetime import date

from marshmallow import Schema, fields, post_load, ValidationError, validates_schema
from marshmallow_oneofschema import OneOfSchema

from nisse.utils.string_helper import get_full_class_name
from nisse.utils.validation_helper import is_number, validate_date


class SlackUser(object):

    def __init__(self, id, name):
        self.id = id
        self.name = name


class Channel(object):

    def __init__(self, id, name):
        self.id = id
        self.name = name


class TimeReportingForm(object):

    def __init__(self, project, day, hours, minutes, comment):
        self.project = project
        self.day = day
        self.hours = hours
        self.minutes = minutes
        self.comment = comment


class ReportGenerateForm(object):

    def __init__(self, project, day_from, day_to, user: SlackUser=None):
        self.project = project
        self.day_from = day_from
        self.day_to = day_to
        if user:
            self.user = user


class Team(object):

    def __init__(self, id, domain):
        self.id = id
        self.domain = domain


class Option(object):

    def __init__(self, value):
        self.value = value


class Action(object):

    def __init__(self, name, type, value=None, selected_options=None):
        self.name = name
        self.type = type
        self.value = value
        self.selected_options = selected_options


class Payload(object):

    def __init__(self, type, token, action_ts, team: Team, user: SlackUser, channel: Channel, response_url, actions=None, trigger_id=None, messages_ts=None):
        self.type = type
        self.token = token
        self.action_ts = action_ts
        self.team = team
        self.user = user
        self.channel = channel
        self.response_url = response_url
        self.actions = actions
        self.trigger_id = trigger_id
        self.messages_ts = messages_ts

    def handle(self, slack_command_service):
        raise NotImplementedError("Basic type - implementation is delivered by higher types")


class TimeReportingFormPayload(Payload):

    def __init__(self, type, token, action_ts, team: Team, user: SlackUser, channel: Channel, response_url, submission: TimeReportingForm, actions=None, trigger_id=None,
                 messages_ts=None):
        super().__init__(type, token, action_ts, team, user, channel, response_url, actions, trigger_id, messages_ts)
        self.submission = submission

    def handle(self, slack_command_service):
        return slack_command_service.save_submitted_time(self)


class ReportGenerateFormPayload(Payload):

    def __init__(self, type, token, action_ts, team: Team, user: SlackUser, channel: Channel, response_url, submission: ReportGenerateForm, actions=None, trigger_id=None,
                 messages_ts=None):
        super().__init__(type, token, action_ts, team, user, channel, response_url, actions, trigger_id, messages_ts)
        self.submission = submission

    def handle(self, slack_command_service):
        return slack_command_service.report_generate_command(self)


class ListCommandPayload(Payload):

    def handle(self, slack_command_service):
        return slack_command_service.list_command_time_range_selected(self)


class DeleteCommandPayload(Payload):

    def handle(self, slack_command_service):
        return slack_command_service.delete_command_project_selected(self)


class DeleteTimeEntryPayload(Payload):

    def handle(self, slack_command_service):
        return slack_command_service.delete_command_time_entry_selected(self)


class DeleteConfirmPayload(Payload):

    def handle(self, slack_command_service):
        return slack_command_service.delete_command_time_entry_confirm_remove(self)


class RemindTimeReportBtnPayload(Payload):

    def handle(self, slack_command_service):
        return slack_command_service.submit_time_dialog_reminder(self)


class UserSchema(Schema):
    id = fields.String()
    name = fields.String()

    @post_load
    def make_obj(self, data):
        return SlackUser(**data)


class ChannelSchema(Schema):
    id = fields.String()
    name = fields.String()

    @post_load
    def make_obj(self, data):
        return Channel(**data)


def check_duration_hours(duration):
    if not is_number(duration) or int(duration) > 12:
        raise ValidationError("Use integers, e.g. 2 up to 12", ["hours"])

def check_duration_minutes(duration):
    if not is_number(duration) or (int(duration) % 15 != 0):
        raise ValidationError("Use integers 0|15|30|45 only", ["minutes"])

def check_date(day):
    if not validate_date(day):
        raise ValidationError('Provide date in format year-month-day e.g. {}'.format(date.today().isoformat()), ["day"])


class TimeReportingFormSchema(Schema):
    project = fields.String()
    day = fields.String(validate=check_date)
    hours = fields.String(validate=check_duration_hours)
    minutes = fields.String(validate=check_duration_minutes)
    comment = fields.String()

    @post_load
    def make_obj(self, data):
        return TimeReportingForm(**data)


class ReportGenerateFormSchema(Schema):
    project = fields.String(allow_none=True)
    day_from = fields.String(validate=check_date)
    day_to = fields.String(validate=check_date)
    user = fields.String(allow_none=True)

    @post_load
    def make_obj(self, data):
        return ReportGenerateForm(**data)


class TeamSchema(Schema):
    id = fields.String()
    domain = fields.String()

    @post_load
    def make_obj(self, data):
        return Team(**data)


class OptionSchema(Schema):
    value = fields.String()

    @post_load
    def make_obj(self, data):
        return Option(**data)


class ActionSchema(Schema):
    name = fields.String()
    type = fields.String()
    value = fields.String(required=False)
    selected_options = fields.List(fields.Nested(OptionSchema), allow_none=True)

    @post_load
    def make_obj(self, data):
        return Action(**data)


class PayloadSchema(Schema):
    type = fields.String()
    token = fields.String()
    action_ts = fields.String()
    team = fields.Nested(TeamSchema)
    user = fields.Nested(UserSchema)
    channel = fields.Nested(ChannelSchema)
    response_url = fields.String()
    actions = fields.List(fields.Nested(ActionSchema), allow_none=True)
    trigger_id = fields.String()
    messages_ts = fields.String()


class TimeReportingFormPayloadSchema(PayloadSchema):
    submission = fields.Nested(TimeReportingFormSchema)

    @post_load
    def make_obj(self, data):
        return TimeReportingFormPayload(**data)


class ReportGenerateFormPayloadSchema(PayloadSchema):
    submission = fields.Nested(ReportGenerateFormSchema)

    @post_load
    def make_obj(self, data):
        return ReportGenerateFormPayload(**data)


class ListCommandPayloadSchema(PayloadSchema):

    @post_load
    def make_obj(self, data):
        return ListCommandPayload(**data)


class DeleteCommandPayloadSchema(PayloadSchema):

    @post_load
    def make_obj(self, data):
        return DeleteCommandPayload(**data)


class DeleteTimeEntryPayloadSchema(PayloadSchema):

    @post_load
    def make_obj(self, data):
        return DeleteTimeEntryPayload(**data)


class DeleteConfirmPayloadSchema(PayloadSchema):

    @post_load
    def make_obj(self, data):
        return DeleteConfirmPayload(**data)


class RemindTimeReportBtnPayloadSchema(PayloadSchema):

    @post_load
    def make_obj(self, data):
        return RemindTimeReportBtnPayload(**data)


class GenericPayloadSchema(OneOfSchema):
    type_field = 'callback_id'
    type_schemas = {
        get_full_class_name(TimeReportingFormPayload): TimeReportingFormPayloadSchema,
        get_full_class_name(ReportGenerateFormPayload): ReportGenerateFormPayloadSchema,
        get_full_class_name(ListCommandPayload): ListCommandPayloadSchema,
        get_full_class_name(DeleteCommandPayload): DeleteCommandPayloadSchema,
        get_full_class_name(DeleteTimeEntryPayload): DeleteTimeEntryPayloadSchema,
        get_full_class_name(DeleteConfirmPayload): DeleteConfirmPayloadSchema,
        get_full_class_name(RemindTimeReportBtnPayload): RemindTimeReportBtnPayloadSchema
    }

    def get_obj_type(self, obj):
        return get_full_class_name(obj)
