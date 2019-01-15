from logging import Logger

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.slack.message import Attachment, Message
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.exception import DataException
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService


class ReminderCommandHandler(SlackCommandHandler):
    @inject
    def __init__(self, config: Config, logger: Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)

    def reminder_show(self, command_body, arguments, action):

        command_name = command_body["command"]
        user = self.get_user_by_slack_user_id(command_body['user_id'])

        day_configuration = self.reminder_service.get_user_reminder_config(user)

        attachments = [
            Attachment(
                text=day_time,
                color="#D72B3F" if "OFF" in day_time else "#3AA3E3",
                attachment_type="default",
                mrkdwn_in=["text"]
            ) for day_time in day_configuration
        ]
        attachments.append(
            Attachment(
                text="",
                footer=self.config['MESSAGE_REMINDER_SET_TIP'].format(command_name),
                mrkdwn_in=["text", "footer"]
            )
        )
        return Message(
            text="Your reminder time is as follow:",
            response_type="ephemeral",
            mrkdwn=True,
            attachments=attachments
        ).dump()

    def reminder_set(self, command_body, arguments, action):

        user = self.get_user_by_slack_user_id(command_body['user_id'])

        index = command_body['text'].find('set') + len('set ')

        if self.reminder_service.set_user_reminder_config(user, command_body['text'][index:]):
            return "Remind times set"
        else:
            raise DataException(field="user",
                                message="incorrect format. Examples: /reminder set 15:15 /reminder set mon:15:15;tue:13:14;sat:18:10 ")

    def dispatch_reminder(self, command_body, arguments, action):
        if not arguments or arguments[0] == "show":
            return self.reminder_show(command_body, arguments, action)
        if arguments[0] == "set":
            return self.reminder_set(command_body, arguments, action)