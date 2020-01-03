import logging
from datetime import datetime
from decimal import Decimal
from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models.slack.dialog import Dialog
from nisse.models.slack.payload import Payload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.food_order_service import FoodOrderService
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.utils.string_helper import get_user_name

class FoodHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService,
                 food_order_service: FoodOrderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)
        self.food_order_service = food_order_service

    def handle(self, payload: Payload):
        if payload.type == 'dialog_submission':
            user = self.get_user_by_slack_user_id(payload.user.id)
            order = self.food_order_service.get_order_by_date_and_channel(datetime.today(), payload.channel.name)

            if order is None:
                raise RuntimeError("Order not exists")

            ordered_item = self.food_order_service.create_food_order_item(
                order, user, payload.submission.ordered_item,
                Decimal(payload.submission.ordered_item_price.replace(",",".")))
            if ordered_item is None:
                raise RuntimeError("Could not order meal")

            resp = self.slack_client.api_call(
                "chat.postMessage",
                channel=payload.channel.name,
                text=get_user_name(user) + " ordered: " + ordered_item.description + " for " + str(
                    ordered_item.cost) + "PLN :knife_fork_plate:"
            )
            if not resp["ok"]:
                self.logger.error(resp)
            return False
        else:
            raise RuntimeError("Unsupported action for food order prompt")

    def create_dialog(self, command_body, argument, action) -> Dialog:
        pass