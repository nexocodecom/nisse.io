import logging
from datetime import datetime, timedelta
from decimal import Decimal

from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient

from nisse.models import FoodOrderItem
from nisse.models.slack.dialog import Dialog
from nisse.models.slack.message import Attachment, Action
from nisse.models.slack.payload import FoodOrderPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.food_order_service import FoodOrderService
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.user_service import UserService
from nisse.utils import string_helper

from nisse.utils.string_helper import get_user_name

# cannot be less than 60 seconds: see 'Restrictions' in https://api.slack.com/methods/chat.deleteScheduledMessage
CHECKOUT_REMINDER_IN = timedelta(minutes=15)


class FoodCommandHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService,
                 food_order_service: FoodOrderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)
        self.food_order_service = food_order_service

    def order_start(self, command_body, arguments: list, action):
        if len(arguments) == 0:
            return "Use format: */ni food _URL_*"

        ordering_link = arguments[0]
        user = self.get_user_by_slack_user_id(command_body['user_id'])

        self.food_order_service.remove_incomplete_food_order_items(datetime.today(), command_body['channel_name'])

        post_at: int = round((datetime.now() + CHECKOUT_REMINDER_IN).timestamp())
        reminder_response = self.slack_client.api_call(
            "chat.scheduleMessage",
            channel=command_body['channel_name'],
            user=user.slack_user_id,
            post_at=post_at,
            text="@{} Looks like you forgot to order from {}.\nUrge your friends to place an order and call */ni order*"
                .format(command_body['user_name'], ordering_link),
            link_names=True
        )
        if not reminder_response["ok"]:
            self.logger.error(reminder_response)
            raise RuntimeError('failed')

        scheduled_message_id = reminder_response['scheduled_message_id']
        order = self.food_order_service.create_food_order(user, datetime.today(), ordering_link, scheduled_message_id,
                                                          command_body['channel_name'])
        self.logger.info("Created order %d for user %s with reminder %s", order.food_order_id,
                         command_body['user_name'], scheduled_message_id)

        order_prompt_response = self.slack_client.api_call(
            "chat.postMessage",
            channel=command_body['channel_name'],
            mrkdwn=True,
            as_user=True,
            attachments=[
                Attachment(
                    callback_id=string_helper.get_full_class_name(FoodOrderPayload),
                    attachment_type="default",
                    text=get_user_name(user) + " orders from " + ordering_link,
                    color="#3AA3E3",
                    actions=[
                        Action(name="order-prompt", text="I'm ordering right now", type="button",
                               value="order-" + str(order.food_order_id)),
                        Action(name="order-prompt", text="Not today", type="button",
                               value="pas-" + str(order.food_order_id)),
                    ]
                ).dump()]
        )
        if not order_prompt_response["ok"]:
            self.logger.error(order_prompt_response)
            raise RuntimeError('failed')
        return None

    def order_checkout(self, command_body, arguments: list, action):
        user = self.get_user_by_slack_user_id(command_body['user_id'])
        reminder = self.food_order_service.checkout_order(user, datetime.today(), command_body['channel_name'])
        self.cancel_reminder(command_body, reminder)

        if not reminder:
            self.logger.warning("User {} can't check out order for this channel".format(user.username))
            self.slack_client.api_call(
                "chat.postEphemeral",
                channel=command_body['channel_name'],
                user=user.slack_user_id,
                text="You can't check out order for this channel. Are you order owner?"
            )
            return

        order_items: [FoodOrderItem] = self.food_order_service.get_food_order_items_by_date(user, datetime.today(),
                                                                                            command_body[
                                                                                                'channel_name'])
        order_items_text = ''
        total_order_cost = Decimal(0.0)
        if order_items:
            for order_item in order_items:
                eating_user = self.user_service.get_user_by_id(order_item.eating_user_id)
                order_items_text += get_user_name(eating_user) + " - " + order_item.description + " (" + str(
                    order_item.cost) + " PLN)\n"
                total_order_cost += order_item.cost
            order_items_text += "\nTotal cost: " + str(total_order_cost) + " PLN"

        if total_order_cost == Decimal(0):
            self.slack_client.api_call(
                "chat.postMessage",
                channel=command_body['channel_name'],
                mrkdwn=True,
                attachments=[
                    Attachment(attachment_type="default",
                               text=str("*{} checked out order. No orders for today.*".format(get_user_name(user))),
                               color="#3AA3E3").dump()])
        else:
            self.slack_client.api_call(
                "chat.postMessage",
                channel=command_body['channel_name'],
                mrkdwn=True,
                attachments=[
                    Attachment(attachment_type="default",
                               text=str("*{} checked out order:*\n" + order_items_text).format(get_user_name(user)),
                               color="#3AA3E3").dump()])

    def cancel_reminder(self, command_body, reminder):
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

    def show_debt(self, command_body, arguments: list, action):
        requesting_user = self.user_service.get_user_by_slack_id(command_body['user_id'])
        debts = list(filter(lambda d: d.debt != 0, self.food_order_service.get_debt(requesting_user)))

        if not debts:
            self.slack_client.api_call(
                "chat.postEphemeral",
                channel=command_body['channel_name'],
                user=requesting_user.slack_user_id,
                mrkdwn=True,
                as_user=True,
                attachments=[
                    Attachment(attachment_type="default",
                               text="You have no debts. Good for you :raised_hands:",
                               color="#3AA3E3").dump()])
        else:
            resp = self.slack_client.api_call(
                "chat.postEphemeral",
                channel=command_body['channel_name'],
                user=requesting_user.slack_user_id,
                mrkdwn=True,
                as_user=True,
                attachments=self.prepare_debts_list(debts)
            )
            if not resp["ok"]:
                self.logger.error(resp)
                print(resp)
                raise RuntimeError('failed')
            return None

    def prepare_debts_list(self, debts):
        attachments = []
        for debt in debts:
            user = self.user_service.get_user_by_id(debt.user_id)
            phone_text = "\nPay with BLIK using phone number: *" + user.phone + "*" if user.phone else ''

            actions = []
            debt_text = "You owe " + str(debt.debt) + " PLN for " + get_user_name(user) + phone_text
            if debt.debt < 0:
                actions.append(Action(name="debt-pay", text="I just paid " + str(-debt.debt) + " PLN", type="button",
                                      value="pay-" + str(debt.user_id)))
                debt_text = "You owe " + str(-debt.debt) + " PLN for " + get_user_name(user) + phone_text
            elif debt.debt > 0:
                debt_text = get_user_name(user) + " owes you " + str(debt.debt) + " PLN"

            attachments.append(Attachment(
                callback_id=string_helper.get_full_class_name(FoodOrderPayload),
                attachment_type="default",
                text=debt_text,
                color="#3AA3E3",
                actions=actions).dump())
        return attachments

    def create_dialog(self, command_body, argument, action) -> Dialog:
        pass