import logging
from datetime import timedelta, date
from decimal import Decimal
from threading import Thread
from typing import Dict

from slackclient import SlackClient

from nisse.models.DTO import TimeRecordDto, PrintParametersDto
from nisse.models.slack.common import ActionType, LabelSelectOption, Option
from nisse.models.slack.dialog import Element, Dialog, DialogSchema
from nisse.models.slack.message import Action, Attachment, Message, TextSelectOption
from nisse.models.slack.payload import Payload, TimeReportingFormPayload, ReportGenerateFormPayload, \
    ReportGenerateDialogPayload, ListCommandPayload, DeleteCommandPayload, DeleteTimeEntryPayload, \
    DeleteConfirmPayload, RemindTimeReportBtnPayload
from nisse.services.exception import DataException, SlackUserException
from nisse.services.project_service import ProjectService
from nisse.services.user_service import *
from nisse.services.reminder_service import ReminderService
from nisse.services.report_service import ReportService
from nisse.services.xlsx_document_service import XlsxDocumentService
from nisse.utils.date_helper import get_start_end_date, get_float_duration
from nisse.utils import slack_model_helper as smh
from nisse.utils import string_helper
from nisse.utils.validation_helper import *
import os
from werkzeug.utils import secure_filename
import uuid
from flask import Flask, current_app
from flask.config import Config

DAILY_HOUR_LIMIT = 20
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

    def submit_time_dialog(self, command_body, arguments, action):
        trigger_id = command_body['trigger_id']
        slack_user_id = command_body['user_id']
        report_date = datetime.datetime.now().date().strftime("%Y-%m-%d")

        self.open_time_reporting_dialog(slack_user_id, trigger_id, report_date)

        return None

    def open_time_reporting_dialog(self, slack_user_id, trigger_id, report_date):
        slack_user_details = self.get_user_by_slack_user_id(slack_user_id)

        project_options_list: List[LabelSelectOption] = self.get_projects_option_list_as_label(slack_user_details.user_id)
        user_default_project_id: str = self.get_default_project_id(project_options_list[0].value, slack_user_details)
        

        dialog: Dict = smh.create_time_reporting_dialog_model(report_date, user_default_project_id,
                                                                                   project_options_list).dump()

        resp = self.slack_client.api_call("dialog.open", trigger_id=trigger_id, dialog=dialog)
        if not resp["ok"]:
            self.logger.error("Can't open dialog submit time: " + resp.get("error"))

    def save_submitted_time(self, form: TimeReportingFormPayload):
        time_record = TimeRecordDto(
            day=form.submission.day,
            hours=int(form.submission.hours),
            minutes=int(form.submission.minutes),
            comment=form.submission.comment,
            project=form.submission.project,
            user_id=form.user.id
        )

        self.save_submitted_time_task(time_record)

    def save_submitted_time_task(self, time_record: TimeRecordDto):

        user = self.get_user_by_slack_user_id(time_record.user_id)

        im_channel = self.slack_client.api_call("im.open", user=time_record.user_id)

        if not im_channel["ok"]:
            self.logger.error("Can't open im channel for: " + str(time_record.user_id) + '. ' + im_channel["error"])
            return

        # todo cache projects globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == time_record.project, projects)

        if selected_project is None:
            self.logger.error("Project doesn't exist: " + time_record.project)
            return

        if list_find(lambda p: str(p.project_id) == time_record.project, user.user_projects) is None:
            self.project_service.assign_user_to_project(project=selected_project, user=user)

            # check if submitted hours doesn't exceed the limit
        submitted_time_entries = self.user_service.get_user_time_entries(user.user_id, time_record.get_parsed_date(),
                                                                         time_record.get_parsed_date())
        duration_float: float = get_float_duration(time_record.hours, time_record.minutes)
        if sum([te.duration for te in submitted_time_entries]) + Decimal(duration_float) > DAILY_HOUR_LIMIT:
            self.slack_client.api_call(
                "chat.postMessage",
                channel=im_channel['channel']['id'],
                text="Sorry, but You can't submit more than " + str(DAILY_HOUR_LIMIT) + " hours for one day.",
                as_user=True
            )
            return

        self.project_service.report_user_time(selected_project, user, duration_float, time_record.comment,
                                              time_record.get_parsed_date())

        attachments = [Attachment(
            title='Submitted ' + string_helper.format_duration_decimal(Decimal(duration_float)) + ' hour(s) for ' + \
                  (
                      'Today' if time_record.day == date.today().isoformat() else time_record.day) + ' in ' + selected_project.name,
            text="_" + time_record.comment + "_",
            mrkdwn_in=["text", "footer"],
            footer=self.config['MESSAGE_SUBMIT_TIME_TIP']
        ).dump()]

        resp = self.slack_client.api_call(
            "chat.postMessage",
            channel=im_channel['channel']['id'],
            attachments=attachments,
            as_user=True
        )

        if not resp["ok"]:
            self.logger.error("Can't post message: " + resp.get("error"))

        return

    def list_command_message(self, command_body, arguments, action):

        message_text = "I'm going to list saved time records..."
        inner_user_id = None

        if len(arguments):
            user = arguments[0]
            inner_user_id = self.extract_slack_user_id(user)
            user = self.get_user_by_slack_user_id(inner_user_id)

            message_text = "I'm going to list saved time records for *" + string_helper.get_user_name(user) + "*..."

        return smh.create_select_period_for_listing_model(command_body, inner_user_id,
                                                                         message_text).dump()

    def list_command_time_range_selected(self, form: ListCommandPayload):
        action_key = next(iter(form.actions), None)
        if action_key is None:
            return Message(text='Error, unable to recognize action', response_typ='ephemeral').dump()
        action = form.actions[action_key]
        inner_user_id = action.name
        user_id = form.user.id

        user = self.get_user_by_slack_user_id(user_id)
        inner_user = self.get_user_by_slack_user_id(inner_user_id)

        if inner_user_id != user_id and user.role.role != 'admin':
            return Message(
                text="Sorry, but only admin user can see other users records :face_with_monocle:",
                response_type="ephemeral",
            ).dump()

        next(iter(action.selected_options), None)
        time_range_selected = next(iter(action.selected_options), None).value

        start_end = get_start_end_date(time_range_selected)

        time_records = self.user_service.get_user_time_entries(inner_user.user_id, start_end[0], start_end[1])
        time_records = sorted(time_records, key=lambda te: te.report_date, reverse=True)

        if len(time_records) == 0:
            return Message(
                text="There is no time entries for `" + time_range_selected + "`",
                response_type="ephemeral",
            ).dump()

        projects = {}
        duration_total = 0
        for time in time_records:
            duration_total += time.duration
            if projects.get(time.project.name):
                projects[time.project.name].text += "\n" + string_helper.make_time_string(time)
            else:
                projects[time.project.name] = Attachment(
                    title=time.project.name,
                    text=string_helper.make_time_string(time),
                    color="#3AA3E3",
                    attachment_type="default",
                    mrkdwn_in=["text"]
                )

        projects['total'] = Attachment(
            title="Total",
            text="You reported *" + string_helper.format_duration_decimal(
                duration_total) + "h* for `" + time_range_selected + "`",
            color="#D72B3F",
            attachment_type="default",
            mrkdwn_in=["text"]
        )

        if inner_user_id == user_id:
            projects['footer'] = Attachment(
                text="",
                footer=self.config.config['MESSAGE_LIST_TIME_TIP'],
                mrkdwn_in=["footer"]
            )

        return Message(
            text="These are hours submitted by *" + (
                "You" if inner_user_id == user_id else user.first_name) + "* for `" + time_range_selected + "`",
            mrkdwn=True,
            response_type="ephemeral",
            attachments=list(projects.values())
        ).dump()

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
        action_key = next(iter(form.actions), None)
        action = form.actions[action_key]
        if action and len(action.selected_options):
            selected_period_key = next(iter(action.selected_options), None)
            selected_period = action.selected_options[selected_period_key].value

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

    def reminder_show(self, command_body, arguments, action):
        command_name = command_body["command"]
        user = self.get_user_by_slack_user_id(command_body['user_id'])

        day_configuration = self.reminder_service.get_user_reminder_config(user)

        return smh.create_reminder_info_model(command_name, day_configuration).dump()

    def reminder_set(self, command_body, arguments, action):
        user = self.get_user_by_slack_user_id(command_body['user_id'])

        index = command_body['text'].find('set') + len('set ')

        if self.reminder_service.set_user_reminder_config(user, command_body['text'][index:]):
            return "Remind times set"
        else:
            raise DataException(field="user",
                                message="incorrect format. Examples: /reminder set 15:15 /reminder set mon:15:15;tue:13:14;sat:18:10 ")

    def delete_command_message(self, command_body, arguments, action):
        user = self.user_service.get_user_by_slack_id(command_body['user_id'])

        project_options_list: List[TextSelectOption] = self.get_projects_option_list_as_text(user.user_id)
        user_default_project_id = self.get_default_project_id(project_options_list[0].value, user)

        return smh.create_select_project_model(project_options_list, user_default_project_id).dump()

    def delete_command_project_selected(self, form: Payload):

        project_id_selected = form.actions[0].selected_options[0].value

        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == project_id_selected, projects)

        user = self.get_user_by_slack_user_id(form.user.id)

        last_time_entries: List[TimeEntry] = self.user_service.get_last_ten_time_entries(user.user_id,
                                                                                         selected_project.project_id)

        if len(last_time_entries) == 0:
            return smh.create_delete_not_found_message(selected_project.name).dump()

        return smh.create_select_time_entry_model(last_time_entries, selected_project).dump()

    def delete_command_time_entry_selected(self, form: Payload):
        time_entry_id_selected = form.actions[0].selected_options[0].value

        user = self.get_user_by_slack_user_id(form.user.id)

        time_entry: TimeEntry = self.user_service.get_time_entry(user.user_id, time_entry_id_selected)

        return smh.create_delete_time_entry_model(time_entry).dump()

    def delete_command_time_entry_confirm_remove(self, form: Payload):
        action_selected = form.actions[0]
        if action_selected.name == 'remove':
            user = self.get_user_by_slack_user_id(form.user.id)

            self.user_service.delete_time_entry(user.user_id, int(action_selected.value))

            return smh.create_delete_successful_message().dump()

        return smh.create_delete_cancel_message().dump()

    def submit_time_dialog_reminder(self, form: RemindTimeReportBtnPayload):        
        report_action = form.actions['report']
        report_date = report_action.value if report_action else datetime.datetime.now().date().strftime("%Y-%m-%d")
        self.open_time_reporting_dialog(form.user.id, form.trigger_id, report_date)
        im_channel = self.slack_client.api_call("im.open", user=form.user.id)
        if not im_channel["ok"]:
            self.logger.error("Can't open im channel for: " + str(form.user.id) + '. ' + im_channel["error"])

        resp = self.slack_client.api_call("chat.delete", channel=im_channel['channel']['id'], ts=form.messages_ts,
                                          as_user=True)
        if not resp["ok"]:
            self.logger.error("Can't delete message: " + resp.get("error"))

        return None

    def dayoff_command_message(self, command_body, arguments, action):
        return Message().dump()

    def get_projects_option_list_as_label(self, user_id=None) -> List[LabelSelectOption]:
        # todo cache it globally e.g. Flask-Cache        
        projects = self.project_service.get_projects_by_user(user_id) if user_id else self.project_service.get_projects()
        return [LabelSelectOption(p.name, p.project_id) for p in projects]

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

    def get_default_project_id(self, first_id: str, user) -> str:
        if user is not None:
            user_last_time_entry = self.user_service.get_user_last_time_entry(user.user_id)
            if user_last_time_entry is not None:
                return user_last_time_entry.project.project_id

        return first_id

    @staticmethod
    def help_command_message(command_body, arguments, action):
        return smh.create_help_command_message(command_body).dump()

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
