import logging
from datetime import datetime, timedelta
from pprint import pprint

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.slack.dialog import Dialog, Element
from nisse.models.slack.payload import Payload, FoodOrderPayload, FoodOrderFormPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.food_order_service import FoodOrderService
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.utils import string_helper


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
        pprint(vars(payload))
        # pprint(vars(payload.actions['bar']))
        trigger_id = payload.trigger_id

        if payload.type == 'dialog_submission':
            pprint(vars(payload.submission))
            resp = self.slack_client.api_call(
                "chat.postMessage",
                channel=payload.channel.name,
                text=payload.user.name + " zamówił " + payload.submission.ordered_item + "(" + payload.submission.ordered_item_price + "PLN)"
            )
            if not resp["ok"]:
                self.logger.error(resp)
            return False

        if payload.actions['bar'].value == 'order':
            elements = [
                Element(label="Zamówienie", type="text", name='ordered_item', placeholder="Co zamawiasz?", value='ab'),
                Element(label="Cena", type="text", name='ordered_item_price', placeholder="Cena", value='abc'),
            ]

            dialog: Dialog = Dialog(title="Złóż zamówienie", submit_label="Zamawiam",
                                callback_id=string_helper.get_full_class_name(FoodOrderFormPayload), elements=elements)
            resp = self.slack_client.api_call("dialog.open", trigger_id=trigger_id, dialog=dialog.dump())
            print(resp)
            if not resp["ok"]:
                self.logger.error("Can't open dialog submit time: " + resp.get("error"))
            print("order")
        elif payload.actions['bar'].value == 'pas':
            print("pas")
        return False

    def create_dialog(self, command_body, argument, action) -> Dialog:
        pass

    def order_start(self, command_body, arguments: list, action):
        if len(arguments) == 0:
            raise RuntimeError("argument is required")
        ordering_link = arguments[0]

        post_at: int = round((datetime.now() + timedelta(seconds=30)).timestamp())
        resp2 = self.slack_client.api_call(
            "chat.scheduleMessage",
            channel=command_body['channel_name'],
            post_at=post_at,
            text="@" + command_body['user_name'] + " Looks like you forgot to order",
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
        self.logger.info("Created order %d for user %s", order.food_order_id, command_body['user_name'])

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
                        {"name": "bar", "text": "I order", "type": "button", "value": order.food_order_id},
                        {"name": "bar", "text": "Pas", "type": "button", "value": "pas"},
                    ]
                }
            ]
        )
        if not resp["ok"]:
            self.logger.error(resp)
            raise RuntimeError('failed')
        return None
