from logging import Logger

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.slack.message import Attachment, Message
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService


class ShowHelpCommandHandler(SlackCommandHandler):
    @inject
    def __init__(self, config: Config, logger: Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)

    def create_help_command_message(self, command_body, arguments, action) -> Message:
        command_name = command_body["command"]

        attachments = [
            Attachment(
                text="*{0}* _(without any arguments)_: Submit working time".format(command_name),
                attachment_type="default",
                mrkdwn_in=["text"]
            ),
            Attachment(
                text="*{0} list*: See reported time".format(command_name),
                attachment_type="default",
                mrkdwn_in=["text"]
            ),
            Attachment(
                text="*{0} delete*: Remove reported time".format(command_name),
                attachment_type="default",
                mrkdwn_in=["text"]
            ),
            Attachment(
                text="*{0} reminder*: See reminder settings".format(command_name),
                attachment_type="default",
                mrkdwn_in=["text"]
            ),
            Attachment(
                text="*{0} report*: Generate report file".format(command_name),
                attachment_type="default",
                mrkdwn_in=["text"]
            ),
            Attachment(
                text='*{0} vacation*: Submit free time within range'.format(command_name),
                attachment_type="default",
                mrkdwn_in=['text']
            ),
            Attachment(
                text="*{0} reminder set [_mon:HH:MM,tue:HH:MM..._]*: Configure reminder time for particular day, or several days at once".format(command_name),
                attachment_type="default",
                mrkdwn_in=["text"]
            )
        ]

        return Message(
            text="*Nisse* is used for reporting working time. Following commands are available:",
            mrkdwn=True,
            response_type="default",
            attachments=attachments
        ).dump()
