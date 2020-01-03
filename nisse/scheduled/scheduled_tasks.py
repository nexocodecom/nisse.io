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
import logging
from nisse.utils.string_helper import get_user_name
import atexit
from apscheduler.schedulers.background import BackgroundScheduler


class ScheduledTasks(SlackCommandHandler):

    def create_dialog(self, command_body, argument, action) -> Dialog:
        pass

    def handle(self, payload: Payload):
        pass

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService,
                 food_order_service: FoodOrderService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)
        self.food_order_service = food_order_service
        self.scheduler = BackgroundScheduler()
        self.schedule_all()

    def schedule_all(self):
        # self.scheduler.add_job(func=self.show_debtors, trigger='cron', day_of_week='mon-fri', hour=11, minute=45)
        # self.scheduler.add_job(func=self.remove_pending_orders, trigger='cron', day_of_week='mon-fri', hour=3)
        # self.scheduler.add_job(func=self.show_debtors, trigger="interval", seconds=60)
        # self.scheduler.add_job(func=self.remove_pending_orders, trigger="interval", seconds=60)
        # self.scheduler.start()
        # Shut down the scheduler when exiting the app
        # atexit.register(lambda: self.scheduler.shutdown())
        pass

    def show_debtors(self, command_body, arguments: list, action):
        debtors_str = "It's time for a dinner.\n"
        debtors = self.food_order_service.top_debtors()
        if debtors:
            debtors_str += "Top debtors are:\n"
        for debtor in debtors:
            debtors_str += "{} has total debt {} PLN\n".format(
                get_user_name(self.user_service.get_user_by_id(debtor[0])), debtor[1])
        for channel_name in self.food_order_service.get_all_food_channels() or []:
            self.slack_client.api_call(
                "chat.postMessage",
                channel=channel_name,
                mrkdwn=True,
                attachments=[Attachment(
                    attachment_type="default",
                    text=str(debtors_str),
                    color="#ec4444").dump()])

    def remove_pending_orders(self):
        pending_orders = self.food_order_service.get_all_pending_orders()
        for order in pending_orders or []:
            self.food_order_service.remove_all_items_for_order(order.food_order_id)
