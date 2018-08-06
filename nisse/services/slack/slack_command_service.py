import logging
from datetime import timedelta, date
from decimal import Decimal
from threading import Thread
from typing import Dict

from slackclient import SlackClient

from nisse.models.DTO import TimeRecordDto, PrintParametersDto
from nisse.models.slack.common import ActionType, LabelSelectOption
from nisse.models.slack.dialog import Element, Dialog, DialogSchema
from nisse.models.slack.message import Action, Attachment, Message, TextSelectOption
from nisse.models.slack.payload import Payload, TimeReportingFormPayload, ReportGenerateFormPayload, ListCommandPayload, DeleteCommandPayload, DeleteTimeEntryPayload, \
    DeleteConfirmPayload
from nisse.services.exception import DataException
from nisse.services.project_service import ProjectService
from nisse.services.user_service import *
from nisse.services.reminder_service import ReminderService
from nisse.services.report_service import ReportService
from nisse.services.xlsx_document_service import XlsxDocumentService
from nisse.utils.date_helper import TimeRanges, get_start_end_date
from nisse.utils import slack_model_helper
from nisse.utils import string_helper
from nisse.utils.validation_helper import *
import os
from werkzeug.utils import secure_filename
import uuid
from flask import current_app

DAILY_HOUR_LIMIT = 20
DEFAULT_REMIND_TIME_FOR_NEWLY_ADDED_USER = "16:00"


class SlackCommandService:
    """
    This class handles all calls from slack

    """

    @inject
    def __init__(self, logger: logging.Logger, project_service: ProjectService, user_service: UserService,
                 slack_client: SlackClient, print_db: ReportService, print_output: XlsxDocumentService,
                 reminder_service: ReminderService):
        self.logger = logger
        self.slack_client = slack_client
        self.project_service = project_service
        self.user_service = user_service
        self.print_db = print_db
        self.print_output = print_output
        self.reminder_service = reminder_service
        self.dialog_schema = DialogSchema()

    @staticmethod
    def create_time_reporting_dialog(default_project_id: str, project_options_list, default_day) -> Dict:
        dialog: Dialog = slack_model_helper.create_time_reporting_dialog_model(default_day, default_project_id, project_options_list)
        return dialog.dump()

    def submit_time_dialog(self, command_body, arguments, action):
        trigger_id = command_body['trigger_id']
        slack_user_id = command_body['user_id']

        self.open_time_reporting_dialog(slack_user_id, trigger_id)

        return None

    def open_time_reporting_dialog(self, slack_user_id, trigger_id):
        project_options_list: List[LabelSelectOption] = self.get_projects_option_list_as_label()
        slack_user = self.get_user_by_slack_user_id(slack_user_id)
        user_default_project_id: str = self.get_default_project_id(project_options_list[0].value, slack_user)
        today = date.today().isoformat()

        dialog: Dict = SlackCommandService.create_time_reporting_dialog(user_default_project_id, project_options_list, today)
        resp = self.slack_client.api_call("dialog.open", trigger_id=trigger_id, dialog=dialog)
        if not resp["ok"]:
            self.logger.error("Can't open dialog submit time: " + resp.get("error"))

    def save_submitted_time(self, form: TimeReportingFormPayload):
        time_record = TimeRecordDto(
            day=form.submission.day,
            duration=form.submission.duration,
            comment=form.submission.comment,
            project=form.submission.project,
            user_id=form.user.id
        )

        # continue work in separate thread to not delay response
        task = Thread(target=self.save_submitted_time_task, args={time_record})
        task.start()

        # return response to slack as soon as possible
        return None

    def save_submitted_time_task(self, time_record:TimeRecordDto):
        slack_user_details = self.slack_client.api_call("users.info", user=time_record.user_id)

        if not slack_user_details['ok']:
            logging.error("Failed to get user detail for slack user: " + time_record.user_id)
            return

        im_channel = self.slack_client.api_call("im.open", user=time_record.user_id)

        if not im_channel["ok"]:
            self.logger.error("Can't open im channel for: " + str(time_record.user_id) + '. ' + im_channel["error"])
            return

        user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                    slack_user_details['user']['profile']['real_name_normalized'],
                                    slack_user_details['user']['is_owner'])

        # todo cache projects globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == time_record.project, projects)

        if selected_project is None:
            self.logger.error("Project doesn't exist: " + time_record.project)
            return

        if list_find(lambda p: str(p.project_id) == time_record.project, user.user_projects) is None:
            self.project_service.assign_user_to_project(project=selected_project, user=user)

            # check if submitted hours doesn't exceed the limit
        submitted_time_entries = self.user_service.get_user_time_entries(user.user_id, time_record.get_parsed_date(), time_record.get_parsed_date())
        if sum([te.duration for te in submitted_time_entries]) + Decimal(time_record.duration) > DAILY_HOUR_LIMIT:
            self.slack_client.api_call(
                "chat.postMessage",
                channel=im_channel['channel']['id'],
                text="Sorry, but You can't submit more than " + str(DAILY_HOUR_LIMIT) + " hours for one day.",
                as_user=True
            )
            return

        self.project_service.report_user_time(selected_project, user, time_record.duration, time_record.comment, time_record.get_parsed_date())

        attachments = [Attachment(
            title='Submitted ' + time_record.duration + ' hour(s) for ' + \
                  ('Today' if time_record.day == date.today().isoformat() else time_record.day) + ' in ' + selected_project.name,
            text="_" + time_record.comment + "_",
            mrkdwn_in=["text", "footer"],
            footer="Use */ni list* to view submitted records"
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

            slack_inner_user_details = self.slack_client.api_call("users.info", user=inner_user_id)

            if not slack_inner_user_details['ok']:
                return Message(
                    text="Can't fetch slack user info",
                    response_type="ephemeral",
                ).dump()

            message_text = "I'm going to list saved time records for *" + slack_inner_user_details['user']['real_name'] + "*..."

        return slack_model_helper.create_select_period_for_listing_model(command_body, inner_user_id, message_text).dump()

    def list_command_time_range_selected(self, form: ListCommandPayload):
        action = next(iter(form.actions), None)
        inner_user_id = action.name
        user_id = form.user.id
        if inner_user_id != user_id:
            slack_user_details = self.slack_client.api_call("users.info", user=user_id)

            if not slack_user_details['ok']:
                return Message(
                    text="Can't fetch slack user info",
                    response_type="ephemeral",
                ).dump()

            user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                        slack_user_details['user']['profile']['real_name_normalized'],
                                        slack_user_details['user']['is_owner'])
            if user.role.role != 'admin':
                return Message(
                    text="Sorry, but only admin user can see other users records :face_with_monocle:",
                    response_type="ephemeral",
                ).dump()

        user = self.get_user_by_slack_user_id(inner_user_id)

        if user is None:
            return Message(
                text="It looks like, no records have been submitted yet :confused:",
                response_type="ephemeral",
            ).dump()

        next(iter(action.selected_options), None)
        time_range_selected = next(iter(action.selected_options), None).value

        start_end = get_start_end_date(time_range_selected)

        time_records = self.user_service.get_user_time_entries(user.user_id, start_end[0], start_end[1])

        if len(time_records) == 0:
            return Message(
                text="There is no time entries for `" + time_range_selected + "`",
                response_type="ephemeral",
            ).dump()

        projects = {}
        for time in time_records:
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

        if inner_user_id == user_id:
            projects['footer'] = Attachment(
                text="",
                footer="Use */ni delete* to remove record",
                mrkdwn_in=["footer"]
            )

        return Message(
            text="These are hours submitted by *" + ("You" if inner_user_id == user_id else user.first_name) + "* for `" + time_range_selected + "`",
            mrkdwn=True,
            response_type="ephemeral",
            attachments=list(projects.values())
        ).dump()

    def report_dialog(self, command_body, arguments, action):
        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        project_options_list: List[LabelSelectOption] = [LabelSelectOption(label=p.name, value=p.project_id) for p in projects]

        # todo select default project for current user
        default_project: LabelSelectOption = project_options_list[0]

        today = date.today().isoformat()
        previous_week = (date.today() - timedelta(7)).isoformat()

        slack_user_details = self.slack_client.api_call("users.info", user=command_body['user_id'])

        if not slack_user_details['ok']:
            raise DataException(field="user", message="No such user !")

        dialog: Dialog = slack_model_helper.create_generate_report_dialog_model(default_project, previous_week, project_options_list, today)

        # admin see users list
        user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                    slack_user_details['user']['profile']['real_name_normalized'],
                                    slack_user_details['user']['is_owner'])
        if user.role.role == 'admin':
            users = self.user_service.get_users()
            user_options_list = [LabelSelectOption(label=p.first_name, value=p.user_id) for p in users]
            dialog.elements.append(Element(label="User", type="select", name='user', placeholder="Select user", optional="true", options=user_options_list))

        resp = self.slack_client.api_call("dialog.open", trigger_id=command_body['trigger_id'], dialog=dialog.dump())

        if not resp["ok"]:
            self.logger.error("Can't open report dialog: " + resp.get("error"))

        return None

    def report_generate_command(self, form: ReportGenerateFormPayload):
        date_to = form.submission.day_to
        date_from = form.submission.day_from

        selected_user = form.submission.user

        project_id = form.submission.project

        print_param = PrintParametersDto()
        print_param.date_to = date_to
        print_param.date_from = date_from
        print_param.project_id = project_id

        # todo cache projects globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == print_param.project_id, projects)

        if selected_project is None:
            raise DataException(field="project", message="Project doesn't exist")

        slack_user_details = self.slack_client.api_call("users.info", user=form.user.id)

        if not slack_user_details['ok']:
            raise DataException(field="user", message="Cannot generate report for current user")

        # only admin can print for everyone
        user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                    slack_user_details['user']['profile']['real_name_normalized'],
                                    slack_user_details['user']['is_owner'])
        if user.role.role != 'admin':
            print_param.user_id = user.user_id
        # if admin select proper user
        elif selected_user is not None:
            print_param.user_id = selected_user

        # generate report
        path_for_report = os.path.join(current_app.instance_path, current_app.config["REPORT_PATH"],
                                       secure_filename(str(uuid.uuid4())) + ".xlsx")
        load_data = self.print_db.load_report_data(print_param)
        self.print_output.save_report(path_for_report, print_param.date_from, print_param.date_to, load_data,
                                      selected_project.name)

        im_channel = self.slack_client.api_call("im.open", user=form.user.id)

        if not im_channel["ok"]:
            self.logger.error("Can't open im channel for: " + str(selected_user) + '. ' + im_channel["error"])

        resp = self.slack_client.api_call(
            "files.upload",
            channels=im_channel['channel']['id'],
            file=open(path_for_report, 'rb'),
            title="Report for " + selected_project.name + " from " + print_param.date_from,
            filetype="xlsx",
            filename=selected_project.name + "-" + print_param.date_from + '-tt-report.xlsx'
        )

        try:
            os.remove(path_for_report)
        except OSError as err:
            self.logger.error("Cannot delete report file{0}".format(err))

        if not resp["ok"]:
            self.logger.error("Can't send report: " + resp.get("error"))

        return None

    def reminder_show(self, command_body, arguments, action):
        command_name = command_body["command"]
        slack_user_details = self.slack_client.api_call("users.info", user=command_body['user_id'])

        if not slack_user_details['ok']:
            raise DataException(field="user", message="No such user !")

        user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                    slack_user_details['user']['profile']['real_name_normalized'],
                                    slack_user_details['user']['is_owner'])
        day_configuration = self.reminder_service.get_user_reminder_config(user)

        return slack_model_helper.create_reminder_info_model(command_name, day_configuration).dump()

    def reminder_set(self, command_body, arguments, action):
        slack_user_details = self.slack_client.api_call(
            "users.info",
            user=command_body['user_id']
        )

        if not slack_user_details['ok']:
            raise DataException(field="user", message="No such user !")

        user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                    slack_user_details['user']['profile']['real_name_normalized'],
                                    slack_user_details['user']['is_owner'])

        index = command_body['text'].find('set') + len('set ')

        if self.reminder_service.set_user_reminder_config(user, command_body['text'][index:]):
            return "Remind times set"
        else:
            raise DataException(field="user", message="incorrect format. Examples: /reminder set 15:15 /reminder set mon:15:15;tue:13:14;sat:18:10 ")

    def delete_command_message(self, command_body, arguments, action):
        project_options_list: List[TextSelectOption] = self.get_projects_option_list_as_text()
        user_default_project_id = self.get_default_project_id(project_options_list[0].value, self.get_user_by_slack_user_id(command_body['user_id']))

        return slack_model_helper.create_select_project_model(project_options_list, user_default_project_id).dump()

    def delete_command_project_selected(self, form: Payload):

        project_id_selected = form.actions[0].selected_options[0].value

        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == project_id_selected, projects)

        user = self.get_user_by_slack_user_id(form.user.id)

        if user is None:
            return Message(
                text="You didn't submit any hours yet :face_with_raised_eyebrow:",
                response_type="ephemeral"
            ).dump()

        last_time_entries: List[TimeEntry] = self.user_service.get_last_ten_time_entries(user.user_id, selected_project.project_id)

        if len(last_time_entries) == 0:
            return Message(
                text="Can't find any time entries for *" + selected_project.name + "* :face_with_rolling_eyes:",
                response_type="ephemeral",
                mrkdwn=True
            ).dump()

        return slack_model_helper.create_select_time_entry_model(last_time_entries, selected_project).dump()

    def delete_command_time_entry_selected(self, form: Payload):
        time_entry_id_selected = form.actions[0].selected_options[0].value

        user = self.get_user_by_slack_user_id(form.user.id)
        time_entry: TimeEntry = self.user_service.get_time_entry(user.user_id, time_entry_id_selected)

        return slack_model_helper.create_delete_time_entry_model(time_entry).dump()

    def delete_command_time_entry_confirm_remove(self, form: Payload):
        action_selected = form.actions[0]
        if action_selected.name == 'remove':
            user = self.get_user_by_slack_user_id(form.user.id)
            self.user_service.delete_time_entry(user.user_id, int(action_selected.value))

            return Message(
                text="Time entry removed! :wink:",
                response_type="ephemeral",
            ).dump()

        return Message(
            text="Canceled :wink:",
            response_type="ephemeral",
        ).dump()

    def submit_time_dialog_reminder(self, form: Payload):
        self.open_time_reporting_dialog(form.user.id, form.trigger_id)
        im_channel = self.slack_client.api_call("im.open", user=form.user.id)
        if not im_channel["ok"]:
            self.logger.error("Can't open im channel for: " + str(form.user.id) + '. ' + im_channel["error"])

        resp = self.slack_client.api_call("chat.delete", channel=im_channel['channel']['id'], ts=form.messages_ts, as_user=True)
        if not resp["ok"]:
            self.logger.error("Can't delete message: " + resp.get("error"))

        return None

    def get_projects_option_list_as_label(self) -> List[LabelSelectOption]:
        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        return [LabelSelectOption(p.name, p.project_id) for p in projects]

    def get_projects_option_list_as_text(self) -> List[TextSelectOption]:
        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        return [TextSelectOption(p.name, p.project_id) for p in projects]

    def get_user_by_slack_user_id(self, slack_user_id):
        slack_user_details = self.slack_client.api_call(
            "users.info",
            user=slack_user_id
        )

        if not slack_user_details['ok']:
            self.logger.error("Can't get user details. Error: " + slack_user_details.get("error"))
            raise ValueError('Retrieve slack user detail failed, user_id: ' + slack_user_id)

        return self.user_service.get_user_by_email(slack_user_details['user']['profile']['email'])

    def get_default_project_id(self, first_id: str, user) -> str:
        if user is not None:
            user_last_time_entry = self.user_service.get_user_last_time_entry(user.user_id)
            if user_last_time_entry is not None:
                return user_last_time_entry.project.project_id

        return first_id

    @staticmethod
    def help_command_message(command_body, arguments, action):
        return slack_model_helper.create_help_command_message(command_body).dump()

    def get_or_add_user(self, user_email, user_name, is_owner=False):
        user = self.user_service.get_user_by_email(user_email)
        if user is None:
            user_role = USER_ROLE_ADMIN if is_owner else USER_ROLE_USER
            user = self.user_service.add_user(user_email, user_name, self.user_service.get_default_password(),
                                              user_role)
            self.reminder_service.set_user_reminder_config(user, DEFAULT_REMIND_TIME_FOR_NEWLY_ADDED_USER)
        return user

    @staticmethod
    def extract_slack_user_id(user):
        if user is not None and user.startswith("<") and user.endswith(">") and user[1] == "@":
            return user[2:-1].split('|')[0]
        else:
            return None
