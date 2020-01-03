import logging
from datetime import datetime

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.slack.dialog import Element, Dialog
from nisse.models.slack.payload import Payload, FoodOrderFormPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.food_order_service import FoodOrderService
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.utils import string_helper


class FoodItemHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService,
                 food_order_service: FoodOrderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)
        self.food_order_service = food_order_service

    def handle(self, payload: Payload):
        if payload.type == 'interactive_message':
            resp = self.slack_client.api_call("dialog.open", trigger_id=payload.trigger_id,
                                              dialog=self.create_order_dialog().dump())
            if not resp["ok"]:
                self.logger.error("Can't open order item selection dialog: " + resp.get("error"))
        elif 'order-prompt' in payload.actions and payload.actions['order-prompt'].value.startswith('pas-'):
            order = self.food_order_service.get_order_by_date_and_channel(datetime.today(), payload.channel.name)
            user = self.get_user_by_slack_user_id(payload.user.id)
            if order is None or order.reminder is None or order.reminder == '':
                self.slack_client.api_call(
                    "chat.postEphemeral",
                    user=user.slack_user_id,
                    channel=payload.channel.name,
                    text="Ordering is closed for today. Try tomorrow :relieved:"
                )
            else:
                order_id = payload.actions['order-prompt'].value.replace("pas-", "")
                self.food_order_service.skip_food_order_item(order_id, user)
                resp = self.slack_client.api_call(
                    "chat.postMessage",
                    channel=payload.channel.name,
                    text=payload.user.name + " is not ordering today."
                )
                if not resp["ok"]:
                    self.logger.error(resp)

        elif 'order-prompt' in payload.actions and payload.actions['order-prompt'].value.startswith('order-'):
            order = self.food_order_service.get_order_by_date_and_channel(datetime.today(), payload.channel.name)
            user = self.get_user_by_slack_user_id(payload.user.id)
            if order is None or order.reminder is None or order.reminder == '':
                self.slack_client.api_call(
                    "chat.postEphemeral",
                    user=user.slack_user_id,
                    channel=payload.channel.name,
                    text="Ordering is closed for today. Try tomorrow :relieved:"
                )
        else:
            raise RuntimeError("Unsupported action for food order prompt")
        return False

    def create_order_dialog(self):
        elements = [
            Element(label="Order", type="text", name='ordered_item', placeholder="What do you order?"),
            Element(label="Price", type="text", name='ordered_item_price', placeholder="Price", value='0.00'),
        ]
        dialog: Dialog = Dialog(title="Place an order", submit_label="Order",
                                callback_id=string_helper.get_full_class_name(FoodOrderFormPayload),
                                elements=elements)
        return dialog

    def create_dialog(self, command_body, argument, action) -> Dialog:
        pass
