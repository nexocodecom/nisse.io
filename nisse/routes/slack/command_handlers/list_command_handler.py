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
            'prev_week': 'Previous week',
            'this_month': 'This month',
            'prev_month': 'Previous month'
        }

    def handle(self, form: ListCommandPayload):
        action_key = next(iter(form.actions), None)
        if action_key is None:
            return Message(text='No action key', response_type='ephemeral')

        action = form.actions[action_key]
        inner_user_id = action.name
        user_id = form.user.id

        user = self.get_user_by_slack_user_id(user_id)
        inner_user = self.get_user_by_slack_user_id(inner_user_id)

        next(iter(action.selected_options), None)
        time_range_selected = next(iter(action.selected_options), None).value

        return self.get_user_time_entries(user, inner_user, time_range_selected).dump()

    def list_command_message(self, command_body, arguments, action):
        arg_iter = iter(arguments)
        first_arg = next(arg_iter, None)
        second_arg = next(arg_iter, None)
        inner_user_id = self._extract_slack_user_id(first_arg)
        time_range = first_arg if self.time_ranges.__contains__(first_arg) else second_arg

        if len(arguments) == 1 and inner_user_id:  # one argument, inner_user_id
            return self.create_select_period_for_listing_model(command_body, inner_user_id).dump()

        if len(arguments) == 1 and time_range:  # one argument, time range
            return self.get_by_time_range(command_body, time_range).dump()

        # two arguments, inner_user_id, time_range
        if len(arguments) == 2:
            return self.get_by_user_and_time_range(command_body, inner_user_id, time_range).dump()

        if len(arguments) > 2:
            return self.too_many_parameters().dump()

        return self.create_select_period_for_listing_model(command_body, inner_user_id).dump()

    def too_many_parameters(self):
        message = 'You have too much for me :confused:. I can only handle one or two parameters at once'
        return Message(text=message, response_type='ephemeral', mrkdwn=True)

    def get_by_time_range(self, command_body, selected_time_range):
        time_range = self.time_ranges.get(selected_time_range)
        if time_range is None:
            message_format = 'I am unable to understand `{0}`.\nSeems like it is not any of following: `{1}`.'
            message = message_format.format(
                selected_time_range, '`, `'.join(self.time_ranges.keys()))
            return Message(text=message, response_type='ephemeral', mrkdwn=True)

        return self._get_by_user_and_time_range(command_body, None, time_range)

    def get_by_user_and_time_range(self, command_body, inner_user_id, selected_time_range):
        if inner_user_id is None:
            message = 'I do not know this guy: {0}'.format(inner_user_id)
            return Message(text=message, response_type='ephemeral')

        time_range = self.time_ranges.get(selected_time_range)
        if time_range is None:
            message_format = 'I am unable to understand `{0}`.\nSeems like it is not any of following: `{1}`.'
            message = message_format.format(
                selected_time_range, '`, `'.join(self.time_ranges.keys()))
            return Message(text=message, response_type='ephemeral', mrkdwn=True)

        return self._get_by_user_and_time_range(command_body, inner_user_id, time_range)

    def _get_by_user_and_time_range(self, command_body, inner_user_id, time_range):
        user = self.get_user_by_slack_user_id(command_body['user_id'])
        inner_user = self.get_user_by_slack_user_id(
            inner_user_id) if inner_user_id else user

        return self.get_user_time_entries(user, inner_user, time_range)

    def get_user_time_entries(self, user: User, inner_user: User, time_range):
        user_db_id = user.slack_user_id
        inner_user_db_id = inner_user.slack_user_id
        current_user_name = "You" if inner_user_db_id == user_db_id else "{0} {1}".format(inner_user.first_name, inner_user.last_name).strip()

        if inner_user_db_id != user_db_id and user.role.role != 'admin':
            message = "Sorry, but only admin user can see other users records :face_with_monocle:"
            return Message(text=message, response_type="ephemeral", mrkdwn=True)

        start_end = get_start_end_date(time_range)

        time_records = self.user_service.get_user_time_entries(
            inner_user.user_id, start_end[0], start_end[1])
        time_records = sorted(
            time_records, key=lambda te: te.report_date, reverse=True)

        if len(time_records) == 0:
            message = "*{0}* have not reported anything for `{1}`".format(
                current_user_name, time_range)
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

        total_duration = string_helper.format_duration_decimal(duration_total)
        total_message = "*{0}* reported *{1}* for `{2}`".format(
            current_user_name, total_duration, time_range)

        projects['total'] = Attachment(
            title="Total",
            text=total_message,
            color="#D72B3F",
            attachment_type="default",
            mrkdwn_in=["text"]
        )

        if inner_user_db_id == user_db_id:
            projects['footer'] = Attachment(
                text="",
                footer=self.config['MESSAGE_LIST_TIME_TIP'],
                mrkdwn_in=["footer"]
            )

        message = "These are hours submitted by *{0}* for `{1}`".format(current_user_name, time_range)
        attachments = list(projects.values())

        return Message(text=message, mrkdwn=True, response_type="ephemeral", attachments=attachments)

    def create_select_period_for_listing_model(self, command_body, inner_user_id):
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
            text="I'm going to list saved time records...",
            response_type="ephemeral",
            mrkdwn=True,
            attachments=attachments
        )
