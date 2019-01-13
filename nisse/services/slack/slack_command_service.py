import logging
import os
import uuid

from flask import current_app
from flask.config import Config
from slackclient import SlackClient
from werkzeug.utils import secure_filename

from nisse.models.DTO import PrintParametersDto
from nisse.models.slack.common import LabelSelectOption
from nisse.models.slack.dialog import Element, Dialog, DialogSchema
from nisse.models.slack.message import TextSelectOption
from nisse.models.slack.payload import Payload, ReportGenerateFormPayload, \
    ReportGenerateDialogPayload
from nisse.services.exception import SlackUserException
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.report_service import ReportService
from nisse.services.user_service import *
from nisse.services.xlsx_document_service import XlsxDocumentService
from nisse.utils import slack_model_helper as smh
from nisse.utils import string_helper
from nisse.utils.date_helper import get_start_end_date
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

    def report_pre_dialog(self, command_body, arguments, action):

        message_text = "I'm going to generate report..."
        inner_user_id = None

        if len(arguments):
            user = arguments[0]
            inner_user_id = self.extract_slack_user_id(user)

            self.get_user_by_slack_user_id(inner_user_id)

        return smh.create_select_period_for_reporting_model(command_body, inner_user_id,
                                                                           message_text).dump()

    def report_dialog(self, form: ReportGenerateDialogPayload):

        selected_period = None
        action = next(iter(form.actions.values()))
        if action and len(action.selected_options):
            selected_period = next(iter(action.selected_options), None).value            

        start_end = get_start_end_date(selected_period)

        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        project_options_list: List[LabelSelectOption] = [LabelSelectOption(label=p.name, value=p.project_id) for p in
                                                         projects]

        # admin see users list
        user = self.get_user_by_slack_user_id(form.user.id)

        dialog: Dialog = smh.create_generate_report_dialog_model(start_end[0], project_options_list,
                                                                                start_end[1])

        if action.name:
            prompted_user = self.get_user_by_slack_user_id(action.name)

        if user.role.role == 'admin':
            users = self.user_service.get_users()
            user_options_list = [LabelSelectOption(label=string_helper.get_user_name(p), value=p.user_id) for p in users]
            dialog.elements.append(
                Element(label="User", value=(prompted_user.user_id if prompted_user else None),
                        optional='true', type="select", name='user', placeholder="Select user", options=user_options_list))

        resp = self.slack_client.api_call("dialog.open", trigger_id=form.trigger_id, dialog=dialog.dump())

        if not resp["ok"]:
            self.logger.error("Can't open report dialog: " + resp.get("error"))

        return None

    def report_generate_command(self, form: ReportGenerateFormPayload):

        date_to = form.submission.day_to
        date_from = form.submission.day_from

        selected_user_id = None
        if hasattr(form.submission, 'user'):
            selected_user_id = form.submission.user

        project_id = form.submission.project

        print_param = PrintParametersDto()
        print_param.date_to = date_to
        print_param.date_from = date_from
        print_param.project_id = project_id

        # todo cache projects globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == print_param.project_id, projects)

        user = self.get_user_by_slack_user_id(form.user.id)

        selected_user = None
        if user.role.role != 'admin':
            print_param.user_id = user.user_id
        # if admin select proper user
        elif selected_user_id is not None:
            print_param.user_id = selected_user_id
            selected_user = self.user_service.get_user_by_id(selected_user_id)

        # generate report
        path_for_report = os.path.join(current_app.instance_path, current_app.config["REPORT_PATH"],
                                       secure_filename(str(uuid.uuid4())) + ".xlsx")
        load_data = self.print_db.load_report_data(print_param)
        self.print_output.save_report(path_for_report, print_param.date_from, print_param.date_to, load_data,
                                      selected_project)

        im_channel = self.slack_client.api_call("im.open", user=form.user.id)

        if not im_channel["ok"]:
            self.logger.error("Can't open im channel for: " + str(selected_user_id) + '. ' + im_channel["error"])

        selected_project_name = "all projects"
        if selected_project is not None:
            selected_project_name = selected_project.name

        resp = self.slack_client.api_call(
            "files.upload",
            channels=im_channel['channel']['id'],
            file=open(path_for_report, 'rb'),
            title=string_helper.generate_xlsx_title(selected_user, selected_project_name, print_param.date_from,
                                                    print_param.date_to),
            filetype="xlsx",
            filename=string_helper.generate_xlsx_file_name(selected_user, selected_project_name, print_param.date_from,
                                                           print_param.date_to)
        )

        try:
            os.remove(path_for_report)
        except OSError as err:
            self.logger.error("Cannot delete report file {0}".format(err))

        if not resp["ok"]:
            self.logger.error("Can't send report: " + resp.get("error"))

        return None

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
