import logging
from pprint import pprint

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.slack.dialog import Dialog, Element
from nisse.models.slack.payload import Payload, FoodOrderPayload, FoodOrderFormPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.utils import string_helper


class FoodHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)

    # handle button click
    def handle(self, payload: Payload):
        pprint(vars(payload))
        # pprint(vars(payload.actions['bar']))
        trigger_id = payload.trigger_id

        if payload.type == 'dialog_submission':
            pprint(vars(payload.submission))
            resp = self.slack_client.api_call(
                "chat.postMessage",
                channel = payload.channel.name,
                text = payload.user.name + " zamówił " + payload.submission.ordered_item + "(" + payload.submission.ordered_item_price + "PLN)"
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

    def order_start(self, command_body, arguments, action):
        response = self.slack_client.api_call(
            "chat.postMessage",
            channel=command_body['channel_name'],
            mrkdwn=True,
            as_user=True,
            attachments=[
                {
                    "callback_id": string_helper.get_full_class_name(FoodOrderPayload),
                    "attachment_type": "default",
                    "text": "@" + command_body['user_name'] + " orders from LINK",
                    "color": "#3AA3E3",
                    "actions": [
                        {"name": "bar", "text": "I order", "type": "button", "value": "order"},
                        {"name": "bar", "text": "Pas", "type": "button", "value": "pas"},
                    ]
                }
            ]
        )
        print(response)
        return None
