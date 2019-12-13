import logging
from datetime import datetime, timedelta
from pprint import pprint

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models import FoodOrderItem
from nisse.models.slack.dialog import Dialog, Element
from nisse.models.slack.payload import Payload, FoodOrderPayload, FoodOrderFormPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.food_order_service import FoodOrderService
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.utils import string_helper

# cannot be less than 60 seconds: see 'Restrictions' in https://api.slack.com/methods/chat.deleteScheduledMessage
REMINDER_IN = timedelta(seconds=80)


class FoodHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService,
                 food_order_service: FoodOrderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)
        self.food_order_service = food_order_service

    # handle button click
    def handle(self, payload: Payload):
        trigger_id = payload.trigger_id

        if payload.type == 'dialog_submission':
            user = self.user_service.get_user_by_slack_id(payload.user.id)
            order = self.food_order_service.get_order_by_date(user, datetime.today())

            if order is None:
                raise RuntimeError("Order not exists")

            ordered_item = self.food_order_service.create_food_order_item(order, user, payload.submission.ordered_item, float(payload.submission.ordered_item_price))
            if ordered_item is None:
                raise RuntimeError("Could not order meal")

            resp = self.slack_client.api_call(
                "chat.postMessage",
                channel=payload.channel.name,
                text=payload.user.name + " ordered: " + ordered_item.description + " - " + str(ordered_item.cost) + "PLN"
            )
            if not resp["ok"]:
                self.logger.error(resp)
            return False

        if payload.actions['order-prompt'].value.startswith('pas-'):
            user = self.user_service.get_user_by_slack_id(payload.user.id)
            order_id = payload.actions['order-prompt'].value.replace("pas-","")
            self.food_order_service.skip_food_order_item(order_id, user)
            resp = self.slack_client.api_call(
                "chat.postMessage",
                channel=payload.channel.name,
                text=payload.user.name + " is not ordering today."
            )
            if not resp["ok"]:
                self.logger.error(resp)
        elif payload.actions['order-prompt'].value.startswith('order-'):
            order_id = payload.actions['order-prompt']

            elements = [
                Element(label="Order", type="text", name='ordered_item', placeholder="What do you order?"),
                Element(label="Price", type="text", name='ordered_item_price', placeholder="Price", value='0.00'),
            ]
            dialog: Dialog = Dialog(title="Place an order", submit_label="Order",
                                callback_id=string_helper.get_full_class_name(FoodOrderFormPayload), elements=elements,
                                state=order_id)
            resp = self.slack_client.api_call("dialog.open", trigger_id=trigger_id, dialog=dialog.dump())
            print(resp)
            if not resp["ok"]:
                self.logger.error("Can't open dialog submit time: " + resp.get("error"))
            print("order")
        else:
            raise RuntimeError("Unsupported action for food order prompt")

        return False

    def create_dialog(self, command_body, argument, action) -> Dialog:
        pass

    def order_start(self, command_body, arguments: list, action):
        if len(arguments) == 0:
            raise RuntimeError("argument is required")
        ordering_link = arguments[0]

        post_at: int = round((datetime.now() + REMINDER_IN).timestamp())
        resp2 = self.slack_client.api_call(
            "chat.scheduleMessage",
            channel=command_body['channel_name'],
            post_at=post_at,
            text="@{} Looks like you forgot to order from {}".format(command_body['user_name'], ordering_link),
            link_names=True
        )
        if not resp2["ok"]:
            self.logger.error(resp2)
            raise RuntimeError('failed')
        scheduled_message_id = resp2['scheduled_message_id']

        user = self.user_service.get_user_by_slack_id(command_body['user_id'])
        order = self.food_order_service.create_food_order(
            user, datetime.today(), ordering_link,
            scheduled_message_id)
        self.logger.info(
            "Created order %d for user %s with reminder %s",
            order.food_order_id, command_body['user_name'], scheduled_message_id)

        resp = self.slack_client.api_call(
            "chat.postMessage",
            channel=command_body['channel_name'],
            mrkdwn=True,
            as_user=True,
            attachments=[
                {
                    "callback_id": string_helper.get_full_class_name(FoodOrderPayload),
                    "attachment_type": "default",
                    "text": "@" + command_body['user_name'] + " orders from " + ordering_link,
                    "color": "#3AA3E3",
                    "actions": [
                        {"name": "order-prompt", "text": "I'm ordering right now", "type": "button", "value": "order-" + str(order.food_order_id)},
                        {"name": "order-prompt", "text": "Not today", "type": "button", "value": "pas-" + str(order.food_order_id)},
                    ]
                }
            ]
        )
        if not resp["ok"]:
            self.logger.error(resp)
            raise RuntimeError('failed')
        return None

    def order_checkout(self, command_body, arguments: list, action):
        user = self.user_service.get_user_by_slack_id(command_body['user_id'])

        reminder = self.food_order_service.checkout_order(user, datetime.today())
        if not reminder:
            self.logger.warning('Already checked out')
            self.slack_client.api_call(
                "chat.postMessage",
                channel=command_body['channel_name'],
                text='Already checked out'
            )
            return

        order_items: [FoodOrderItem] = self.food_order_service.get_food_order_items_by_date(user, datetime.today())
        order_items_text = ''
        if order_items:
            for order_item in order_items:
                order_items_text += str(order_item.eating_user_id) + " - " + order_item.description + " (" + str(order_item.cost) + " PLN)"
        #TODO use user.name instead of eating_user_id
        if order_items_text == '':
            self.slack_client.api_call(
                "chat.postMessage",
                channel=command_body['channel_name'],
                text="@{} checked out order\nNo orders for today.".format(command_body['user_name'])
            )
        else:
            self.slack_client.api_call(
                "chat.postMessage",
                channel=command_body['channel_name'],
                text=("@{} checked out order\nSummary:\n"+order_items_text).format(command_body['user_name'])
            )

        self.logger.debug('Canceling reminder %s', reminder)
        resp = self.slack_client.api_call(
            "chat.deleteScheduledMessage",
            channel=command_body['channel_name'],
            scheduled_message_id=reminder,
        )
        if not resp["ok"]:
            self.logger.warning("Problem cancelling reminder '%s': %s", reminder, resp)
        else:
            self.logger.info('Cancelled reminder %s', reminder)
