from datetime import date, datetime

from marshmallow import Schema, fields, post_load, ValidationError
from marshmallow_oneofschema import OneOfSchema

from nisse.utils.date_helper import parse_formatted_date
from nisse.utils.string_helper import get_full_class_name
from nisse.utils.validation_helper import is_number, validate_date


def check_duration_hours(duration):
    if not is_number(duration) or int(duration) > 12:
        raise ValidationError("Use integers, e.g. 2 up to 12", ["hours"])


def check_duration_minutes(duration):
    if not is_number(duration) or (int(duration) % 15 != 0):
        raise ValidationError("Use integers 0|15|30|45 only", ["minutes"])


def check_date_not_from_future(day):
    validate_date(day)
    if parse_formatted_date(day) > datetime.now().date():
        raise ValidationError("Provided date is from the future")


def check_date(day):
    if not validate_date(day):
        raise ValidationError(
            'Provide date in format year-month-day e.g. {}'.format(date.today().isoformat()), ["day"])


class SlackUser(object):

    class Schema(Schema):
        id = fields.String()
        name = fields.String()

        @post_load
        def make_obj(self, data):
            return SlackUser(**data)

    def __init__(self, id, name):
        self.id = id
        self.name = name


class Channel(object):

    class Schema(Schema):
        id = fields.String()
        name = fields.String()

        @post_load
        def make_obj(self, data):
            return Channel(**data)

    def __init__(self, id, name):
        self.id = id
        self.name = name


class TimeReportingForm(object):

    class Schema(Schema):
        project = fields.String()
        day = fields.String(validate=check_date)
        hours = fields.String(validate=check_duration_hours)
        minutes = fields.String(validate=check_duration_minutes)
        comment = fields.String()

        @post_load
        def make_obj(self, data):
            return TimeReportingForm(**data)

    def __init__(self, project, day, hours, minutes, comment):
        self.project = project
        self.day = day
        self.hours = hours
        self.minutes = minutes
        self.comment = comment


class ReportGenerateForm(object):

    class Schema(Schema):

        project = fields.String(allow_none=True)
        day_from = fields.String(validate=check_date)
        day_to = fields.String(validate=check_date_not_from_future)
        user = fields.String(allow_none=True)

        @post_load
        def make_obj(self, data):
            return ReportGenerateForm(**data)

    def __init__(self, project, day_from, day_to, user: SlackUser = None):
        self.project = project
        self.day_from = day_from
        self.day_to = day_to
        if user:
            self.user = user


class Team(object):

    class Schema(Schema):
        id = fields.String()
        domain = fields.String()

        @post_load
        def make_obj(self, data):
            return Team(**data)

    def __init__(self, id, domain):
        self.id = id
        self.domain = domain


class Option(object):

    class Schema(Schema):
        value = fields.String()

        @post_load
        def make_obj(self, data):
            return Option(**data)

    def __init__(self, value):
        self.value = value


class Action(object):

    class Schema(Schema):
        name = fields.String()
        type = fields.String()
        value = fields.String(required=False)
        selected_options = fields.List(
            fields.Nested(Option.Schema), allow_none=True)

        @post_load
        def make_obj(self, data):
            return Action(**data)

    def __init__(self, name, type, value=None, selected_options=None):
        self.name = name
        self.type = type
        self.value = value
        self.selected_options = selected_options


class Payload(object):

    class Schema(Schema):
        type = fields.String()
        token = fields.String()
        action_ts = fields.String()
        team = fields.Nested(Team.Schema)
        user = fields.Nested(SlackUser.Schema)
        channel = fields.Nested(Channel.Schema)
        response_url = fields.String()
        actions = fields.List(fields.Nested(Action.Schema), allow_none=True)
        trigger_id = fields.String()
        messages_ts = fields.String()

        @post_load
        def make_obj(self, data):
            return Payload(**data)

    def __init__(self, type, token, action_ts, team: Team, user: SlackUser, channel: Channel, response_url,
                 actions=None, trigger_id=None, messages_ts=None):
        self.type = type
        self.token = token
        self.action_ts = action_ts
        self.team = team
        self.user = user
        self.channel = channel
        self.response_url = response_url
        self.actions = {x.name: x for x in actions} if actions else None
        self.trigger_id = trigger_id
        self.messages_ts = messages_ts

    def handler_type(self) -> type:
        return None


class TimeReportingFormPayload(Payload):

    class Schema(Payload.Schema):
        submission = fields.Nested(TimeReportingForm.Schema)

        @post_load
        def make_obj(self, data):
            return TimeReportingFormPayload(**data)

    def __init__(self, type, token, action_ts, team: Team, user: SlackUser, channel: Channel, response_url,
                 submission: TimeReportingForm, actions=None, trigger_id=None,
                 messages_ts=None):
        super().__init__(type, token, action_ts, team, user, channel,
                         response_url, actions, trigger_id, messages_ts)
        self.submission = submission

    def handler_type(self) -> type:
        from nisse.routes.slack.command_handlers.submit_time_command_handler import SubmitTimeCommandHandler
        return SubmitTimeCommandHandler


class ReportGenerateFormPayload(Payload):

    class Schema(Payload.Schema):
        submission = fields.Nested(ReportGenerateForm.Schema)

        @post_load
        def make_obj(self, data):
            return ReportGenerateFormPayload(**data)

    def __init__(self, type, token, action_ts, team: Team, user: SlackUser, channel: Channel, response_url,
                 submission: ReportGenerateForm=None, actions=None, trigger_id=None,
                 messages_ts=None):
        super().__init__(type, token, action_ts, team, user, channel,
                         response_url, actions, trigger_id, messages_ts)
        self.submission = submission

    def handler_type(self) -> type:
        from nisse.routes.slack.command_handlers.report_command_handler import ReportCommandHandler
        return ReportCommandHandler


class ListCommandPayload(Payload):

    class Schema(Payload.Schema):

        @post_load
        def make_obj(self, data):
            return ListCommandPayload(**data)

    def handler_type(self) -> type:
        from nisse.routes.slack.command_handlers.list_command_handler import ListCommandHandler
        return ListCommandHandler


class DeleteTimeEntryPayload(Payload):

    class Schema(Payload.Schema):

        @post_load
        def make_obj(self, data):
            return DeleteTimeEntryPayload(**data)

    def handler_type(self) -> type:
        from nisse.routes.slack.command_handlers.delete_time_command_handler import DeleteTimeCommandHandler
        return DeleteTimeCommandHandler


class RemindTimeReportBtnPayload(Payload):

    class Schema(Payload.Schema):
        @post_load
        def make_obj(self, data):
            return RemindTimeReportBtnPayload(**data)

    def handler_type(self) -> type:
        from nisse.routes.slack.command_handlers.submit_time_button_handler import SubmitTimeButtonHandler
        return SubmitTimeButtonHandler


class RequestFreeDaysForm(object):

    class Schema(Payload.Schema):
        start_date = fields.String(validate=check_date)
        end_date = fields.String(validate=check_date)
        event_id = fields.String(allow_none=True)

        @post_load
        def make_obj(self, data):
            return RequestFreeDaysForm(**data)

    def __init__(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date


class RequestFreeDaysPayload(Payload):

    class Schema(Payload.Schema):
        submission = fields.Nested(RequestFreeDaysForm.Schema)

        @post_load
        def make_obj(self, data):
            return RequestFreeDaysPayload(**data)

    def __init__(self, type, token, action_ts, team: Team, user: SlackUser, channel: Channel, response_url,
                 submission: RequestFreeDaysForm=None, actions=None, trigger_id=None, messages_ts=None):
        super().__init__(type, token, action_ts, team, user, channel,
                         response_url, actions, trigger_id, messages_ts)
        self.submission = submission

    def handler_type(self) -> type:
        from nisse.routes.slack.command_handlers.vacation_command_handler import VacationCommandHandler
        return VacationCommandHandler


class ProjectAddForm(object):

    class Schema(Payload.Schema):
        project_name = fields.String()

        @post_load
        def make_obj(self, data):
            return ProjectAddForm(**data)

    def __init__(self, project_name):
        self.project_name = project_name


class ProjectAddPayload(Payload):

    class Schema(Payload.Schema):
        submission = fields.Nested(ProjectAddForm.Schema)

        @post_load
        def make_obj(self, data):
            return ProjectAddPayload(**data)

    def __init__(self, type, token, action_ts, team: Team, user: SlackUser, channel: Channel, response_url,
                 submission: ProjectAddForm=None, actions=None, trigger_id=None, messages_ts=None):
        super().__init__(type, token, action_ts, team, user, channel,
                         response_url, actions, trigger_id, messages_ts)
        self.submission = submission

    def handler_type(self) -> type:
        from nisse.routes.slack.command_handlers.project_command_handler import ProjectCommandHandler
        return ProjectCommandHandler


class GenericPayloadSchema(OneOfSchema):
    type_field = 'callback_id'
    type_schemas = {
        get_full_class_name(TimeReportingFormPayload): TimeReportingFormPayload.Schema,
        get_full_class_name(ReportGenerateFormPayload): ReportGenerateFormPayload.Schema,
        get_full_class_name(ListCommandPayload): ListCommandPayload.Schema,
        get_full_class_name(DeleteTimeEntryPayload): DeleteTimeEntryPayload.Schema,
        get_full_class_name(RemindTimeReportBtnPayload): RemindTimeReportBtnPayload.Schema,
        get_full_class_name(RequestFreeDaysPayload): RequestFreeDaysPayload.Schema,
        get_full_class_name(ProjectAddPayload): ProjectAddPayload.Schema
    }

    def get_obj_type(self, obj):
        return get_full_class_name(obj)
