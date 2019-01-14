import logging

from flask.config import Config
from slackclient import SlackClient

from nisse.models.slack.dialog import DialogSchema
from nisse.models.slack.message import TextSelectOption
from nisse.models.slack.payload import Payload
from nisse.services.exception import SlackUserException
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.report_service import ReportService
from nisse.services.user_service import *
from nisse.services.xlsx_document_service import XlsxDocumentService
from nisse.utils import slack_model_helper as smh
from nisse.utils.validation_helper import *

DEFAULT_REMIND_TIME_FOR_NEWLY_ADDED_USER = "16:00"


class SlackCommandService:
    """
    This class handles all calls from slack

    """

    @inject
    def __init__(self, logger: logging.Logger, project_service: ProjectService, user_service: UserService,
                 slack_client: SlackClient, print_db: ReportService, print_output: XlsxDocumentService,
                 reminder_service: ReminderService, config: Config):
        self.logger = logger
        self.slack_client = slack_client
        self.project_service = project_service
        self.user_service = user_service
        self.print_db = print_db
        self.print_output = print_output
        self.reminder_service = reminder_service
        self.dialog_schema = DialogSchema()
        self.config = config

    def delete_command_message(self, command_body, arguments, action):
        user = self.user_service.get_user_by_slack_id(command_body['user_id'])

        project_options_list: List[TextSelectOption] = self.get_projects_option_list_as_text(user.user_id)
        user_default_project_id = self.get_default_project_id(project_options_list[0].value, user)

        return smh.create_select_project_model(project_options_list, user_default_project_id).dump()

    # TODO move to helper class
    def get_default_project_id(self, first_id: str, user) -> str:
        if user is not None:
            user_last_time_entry = self.user_service.get_user_last_time_entry(user.user_id)
            if user_last_time_entry is not None:
                return user_last_time_entry.project.project_id

        return first_id

    def delete_command_project_selected(self, form: Payload):

        project_id_selected = next(iter(form.actions.values())).selected_options[0].value

        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == project_id_selected, projects)

        user = self.get_user_by_slack_user_id(form.user.id)

        last_time_entries: List[TimeEntry] = self.user_service.get_last_ten_time_entries(user.user_id,
                                                                                         selected_project.project_id)

        if len(last_time_entries) == 0:
            return smh.create_delete_not_found_message(selected_project.name).dump()

        return smh.create_select_time_entry_model(last_time_entries, selected_project).dump()

    def delete_command_time_entry_selected(self, form: Payload):
        time_entry_id_selected = next(iter(form.actions.values())).selected_options[0].value

        user = self.get_user_by_slack_user_id(form.user.id)

        time_entry: TimeEntry = self.user_service.get_time_entry(user.user_id, time_entry_id_selected)

        return smh.create_delete_time_entry_model(time_entry).dump()

    def delete_command_time_entry_confirm_remove(self, form: Payload):
        action_selected = next(iter(form.actions.values()))
        if action_selected.name == 'remove':
            user = self.get_user_by_slack_user_id(form.user.id)

            self.user_service.delete_time_entry(user.user_id, int(action_selected.value))

            return smh.create_delete_successful_message().dump()

        return smh.create_delete_cancel_message().dump()

    def get_projects_option_list_as_text(self, user_id=None) -> List[TextSelectOption]:
        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects_by_user(user_id) if user_id else self.project_service.get_projects()
        return [TextSelectOption(p.name, p.project_id) for p in projects]

    def get_user_by_slack_user_id(self, slack_user_id):

        user = self.user_service.get_user_by_slack_id(slack_user_id)

        if not user:
            slack_user_details = self.slack_client.api_call(
                "users.info",
                user=slack_user_id
            )

            if not slack_user_details['ok']:
                self.logger.error("Can't get user details. Error: " + slack_user_details.get("error"))
                raise SlackUserException('Retrieve slack user detail failed, user_id: ' + slack_user_id)

            user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                 slack_user_details['user']['profile']['real_name_normalized'],
                                 slack_user_id,
                                 slack_user_details['user']['is_owner'])
        return user

    def get_or_add_user(self, user_email, user_name, slack_user_id, is_owner=False):
        user = self.user_service.get_user_by_email(user_email)
        if user is None:
            user_role = USER_ROLE_ADMIN if is_owner else USER_ROLE_USER
            names = user_name.split(" ")
            first_name = names[0]
            last_name = None
            if len(names) > 1:
                last_name = names[1]
            user = self.user_service.add_user(user_email, first_name, last_name, self.user_service.get_default_password(), slack_user_id, user_role)
            self.project_service.assign_user_to_project(Project(project_id=1), user)
            self.reminder_service.set_user_reminder_config(user, DEFAULT_REMIND_TIME_FOR_NEWLY_ADDED_USER)
        return user

    @staticmethod
    def extract_slack_user_id(user):
        if user is not None and user.startswith("<") and user.endswith(">") and user[1] == "@":
            return user[2:-1].split('|')[0]
        else:
            return None
