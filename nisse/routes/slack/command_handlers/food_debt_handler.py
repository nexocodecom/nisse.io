import logging

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.slack.dialog import Dialog
from nisse.models.slack.message import Attachment
from nisse.models.slack.payload import Payload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.food_order_service import FoodOrderService
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService

from nisse.utils.string_helper import get_user_name


class FoodDebtHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService,
                 food_order_service: FoodOrderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)
        self.food_order_service = food_order_service

    def handle(self, payload: Payload):
        if 'debt-pay' in payload.actions and payload.actions['debt-pay'].value.startswith('pay-'):
            settled_user = self.user_service.get_user_by_id(payload.actions['debt-pay'].value.replace("pay-", ""))
            user = self.user_service.get_user_by_slack_id(payload.user.id)

            self.food_order_service.pay_debts(user, settled_user)

            self.slack_client.api_call(
                "chat.postEphemeral",
                channel=payload.channel.name,
                user=user.slack_user_id,
                mrkdwn=True,
                as_user=True,
                attachments=[Attachment(
                    attachment_type="default",
                    text="Lannisters always pay their debts. Glad that you too {} :tada:".format(
                        get_user_name(settled_user)),
                    color="#3AA3E3").dump()])

            self.slack_client.api_call(
                "chat.postEphemeral",
                channel=payload.channel.name,
                mrkdwn=True,
                as_user=True,
                user=settled_user.slack_user_id,
                attachments=[Attachment(
                    attachment_type="default",
                    text="{} paid for you for food :heavy_dollar_sign:".format(get_user_name(user)),
                    color="#3AA3E3").dump()])
        else:
            raise RuntimeError("Unsupported action for food order prompt")
        return False

    def create_dialog(self, command_body, argument, action) -> Dialog:
        pass
