from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.user_service import UserService, User
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from slackclient import SlackClient
from logging import Logger
from flask_injector import inject

from flask.config import Config
from nisse.models.slack.payload import Payload, ListCommandPayload
from nisse.models.slack.message import Action, Attachment, Message, TextSelectOption
from nisse.models.slack.common import ActionType
from nisse.utils import string_helper
from nisse.utils.date_helper import get_start_end_date, get_float_duration, TimeRanges


class ListCommandHandler(SlackCommandHandler):
    @inject
    def __init__(self, logger: Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService, config: Config):
        super().__init__(logger, user_service, slack_client, project_service, reminder_service)
        self.config = config
        self.time_ranges = {
            'today': 'Today',
            'yesterday': 'Yesterday',
            'this2weeks': 'This 2 weeks',
            'this_week': 'This week',
            'previous_week': 'Previous week',
            'this_month': 'This month',
            'previous_month': 'Previous month'
        }

    def handle(self, form: ListCommandPayload):
        action = next(iter(form.actions), None)
        inner_user_id = action.name
        user_id = form.user.id

        user = self.get_user_by_slack_user_id(user_id)
        inner_user = self.get_user_by_slack_user_id(inner_user_id)

        next(iter(action.selected_options), None)
        time_range_selected = next(iter(action.selected_options), None).value

        return self.get_user_time_entries(user, inner_user, time_range_selected).dump()

    def list_command_message(self, command_body, arguments, action):

        message_text = "I'm going to list saved time records..."
        inner_user_id = None

        if len(arguments):
            return self.handle_message_with_args(command_body, arguments).dump()

        return self.create_select_period_for_listing_model(command_body, inner_user_id, message_text).dump()

    def handle_message_with_args(self, command_body, arguments):
        time_range, inner_user_id = None, None
        if len(arguments) == 1:
            time_range = self.time_ranges.get(arguments[0])
        elif len(arguments) == 2:
            time_range = self.time_ranges.get(arguments[0])
            inner_user_id = self._extract_slack_user_id(arguments[1])
        else:
            message = 'You have too much for me :confused:. I can only handle one or two parameters at once'
            return Message(text=message, response_type='ephemeral', mrkdwn=True)

        if time_range is None:
            message_format = 'I am unable to understand `{0}`.\nSeems like it is not any of following: `{1}`.'
            message = message_format.format(
                arguments[0], '`, `'.join(self.time_ranges.keys()))
            return Message(text=message, response_type='ephemeral', mrkdwn=True)

        if len(arguments) == 2 and arguments[1] and inner_user_id is None:
            message = 'I dont know this guy: {0}'.format(arguments[1])
            return Message(text=message, response_type='ephemeral')

        user = self.get_user_by_slack_user_id(command_body['user_id'])
        inner_user = self.get_user_by_slack_user_id(
            inner_user_id) if inner_user_id else user

        return self.get_user_time_entries(user, inner_user, time_range)

    def get_user_time_entries(self, user: User, inner_user: User, time_range_selected):
        user_id = user.slack_user_id
        inner_user_id = inner_user.slack_user_id

        if inner_user_id != user_id and user.role.role != 'admin':
            message = "Sorry, but only admin user can see other users records :face_with_monocle:"
            return Message(text=message, response_type="ephemeral", mrkdwn=True)

        start_end = get_start_end_date(time_range_selected)

        time_records = self.user_service.get_user_time_entries(
            inner_user.user_id, start_end[0], start_end[1])
        time_records = sorted(
            time_records, key=lambda te: te.report_date, reverse=True)

        if len(time_records) == 0:
            message = "There is no time entries for `" + time_range_selected + "`"
            return Message(text=message, response_type="ephemeral", mrkdwn=True)

        projects = {}
        duration_total = 0
        for time in time_records:
            duration_total += time.duration
            if projects.get(time.project.name):
                projects[time.project.name].text += "\n" + \
                    string_helper.make_time_string(time)
            else:
                projects[time.project.name] = Attachment(
                    title=time.project.name,
                    text=string_helper.make_time_string(time),
                    color="#3AA3E3",
                    attachment_type="default",
                    mrkdwn_in=["text"]
                )

        projects['total'] = Attachment(
            title="Total",
            text="You reported *" + string_helper.format_duration_decimal(
                duration_total) + "h* for `" + time_range_selected + "`",
            color="#D72B3F",
            attachment_type="default",
            mrkdwn_in=["text"]
        )

        if inner_user_id == user_id:
            projects['footer'] = Attachment(
                text="",
                footer=self.config['MESSAGE_LIST_TIME_TIP'],
                mrkdwn_in=["footer"]
            )

        message = "These are hours submitted by *" + (
            "You" if inner_user_id == user_id else user.first_name) + "* for `" + time_range_selected + "`"
        attachments = list(projects.values())

        return Message(text=message, mrkdwn=True, response_type="ephemeral", attachments=attachments)

    def create_select_period_for_listing_model(self, command_body, inner_user_id, message_text):
        actions = [
            Action(
                name=inner_user_id if inner_user_id is not None else command_body['user_id'],
                text="Select time range...",
                type=ActionType.SELECT.value,
                options=[TextSelectOption(
                    text=tr.value, value=tr.value) for tr in TimeRanges]
            )
        ]
        attachments = [
            Attachment(
                text="Show record for",
                fallback="Select time range to list saved time records",
                color="#3AA3E3",
                attachment_type="default",
                callback_id=string_helper.get_full_class_name(
                    ListCommandPayload),
                actions=actions
            )
        ]

        return Message(
            text=message_text,
            response_type="ephemeral",
            mrkdwn=True,
            attachments=attachments
        )
