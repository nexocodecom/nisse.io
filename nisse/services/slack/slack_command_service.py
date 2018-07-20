import logging
from calendar import monthrange
from datetime import timedelta, date
from datetime import datetime as dt
from decimal import Decimal
from enum import Enum
from typing import NamedTuple
from slackclient import SlackClient

from nisse.models.DTO import PrintParameters
from nisse.services.project_service import ProjectService
from nisse.services.user_service import *
from nisse.services.reminder_service import ReminderService
from nisse.services.report_service import ReportService
from nisse.services.xlsx_document_service import XlsxDocumentService
from nisse.utils.validation_helper import *
import os
from werkzeug.utils import secure_filename
import uuid
from flask import current_app

CALLBACK_TOKEN_TIME_SUBMIT = "tt-dialog-time-sbt"
CALLBACK_TOKEN_LIST_COMMAND_TIME_RANGE = "tt-list-command-msg-time-range"
CALLBACK_TOKEN_DELETE_COMMAND_PROJECT = "tt-delete-command-msg-project"
CALLBACK_TOKEN_DELETE_COMMAND_TIME_ENTRY = "tt-delete-command-msg-time-entry"
CALLBACK_TOKEN_DELETE_COMMAND_CONFIRM = "tt-delete-command-confirm"
CALLBACK_TOKEN_REPORT_SUBMIT = "tt-report-sbt"
CALLBACK_TOKEN_REMINDER_REPORT_BTN = "tt-reminder-report-btn"

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

    def submit_time_dialog(self, command_body):
        project_options_list = self.get_projects_option_list()
        user_default_project = self.get_default_project_for_user(project_options_list,
                                                                 self.get_user_by_slack_user_id(
                                                                     command_body['user_id']))

        today = date.today().isoformat()

        dialog = {
            "title": "Submitting time",
            "submit_label": "Submit",
            "callback_id": CALLBACK_TOKEN_TIME_SUBMIT,
            "elements": [
                {
                    "label": "Project",
                    "type": "select",
                    "name": "project",
                    "placeholder": "Select a project",
                    "value": user_default_project['value'],
                    "options": project_options_list
                },
                {
                    "label": "Day",
                    "type": "text",
                    "name": "day",
                    "placeholder": "Specify date",
                    "value": today
                },
                {
                    "label": "Duration",
                    "name": "duration",
                    "type": "text",
                    "subtype": "number",
                    "placeholder": "Hours"
                },
                {
                    "label": "Note",
                    "name": "comment",
                    "type": "textarea",
                    "hint": "Provide short description"
                }
            ]
        }

        resp = self.slack_client.api_call(
            "dialog.open",
            trigger_id=command_body['trigger_id'],
            dialog=dialog
        )

        if not resp["ok"]:
            self.logger.error("Can't open dialog submit time: " + resp.get("error"))

        return None, 204

    def save_submitted_time(self, dialog_submission_body):
        time_record = TimeRecord(
            day=dialog_submission_body['submission']['day'],
            duration=dialog_submission_body['submission']['duration'],
            comment=dialog_submission_body['submission']['comment'],
            project=dialog_submission_body['submission']['project'],
        )

        if not is_number(time_record.duration) or float(time_record.duration) < 0 or float(time_record.duration) > 24:
            return {
                       "errors": [
                           {
                               "name": "duration",
                               "error": "Use numbers, e.g. 2 or 2.5 or 2.45 etc"
                           }
                       ]
                   }, 200

        if not validate_date(time_record.day):
            return {
                       "errors": [
                           {
                               "name": "day",
                               "error": "Provide date in format year-month-day, e.g. " + date.today().isoformat()
                           }
                       ]
                   }, 200

        # todo cache projects globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == time_record.project, projects)

        if selected_project is None:
            return {
                       "errors": [
                           {
                               "name": "project",
                               "error": "Project doesn't exist"
                           }
                       ]
                   }, 200

        slack_user_details = self.slack_client.api_call(
            "users.info",
            user=dialog_submission_body['user']['id']
        )

        if not slack_user_details['ok']:
            return {
                       "errors": [
                           {
                               "name": "project",
                               "error": "Can't save time for current user"
                           }
                       ]
                   }, 200

        user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                    slack_user_details['user']['profile']['real_name_normalized'],
                                    slack_user_details['user']['is_owner'])

        if list_find(lambda p: str(p.project_id) == time_record.project, user.user_projects) is None:
            self.project_service.assign_user_to_project(project=selected_project, user=user)

        # check if submitted hours doesn't exceed the limit
        submitted_time_entries = self.user_service.get_user_time_entries(user.user_id,
                                                                         time_record.get_parsed_date(),
                                                                         time_record.get_parsed_date())
        if sum([te.duration for te in submitted_time_entries]) + Decimal(time_record.duration) > DAILY_HOUR_LIMIT:
            return {
                       "errors": [
                           {
                               "name": "day",
                               "error": "You can't submit more than " + str(DAILY_HOUR_LIMIT) + " hours for one day"
                           }
                       ]
                   }, 200

        self.project_service.report_user_time(selected_project,
                                              user,
                                              time_record.duration,
                                              time_record.comment,
                                              time_record.get_parsed_date())

        details = [
            {
                'title': 'Submitted ' + time_record.duration + \
                         ' hour(s) for ' + \
                         ('Today' if time_record.day == date.today().isoformat() else date.today().isoformat()) + \
                         ' in ' + selected_project.name,
                'text': "_" + time_record.comment + "_",
                'mrkdwn_in': ["text", "footer"],
                'footer': "Use */ni list* to view submitted records"
            },
        ]

        im_channel = self.slack_client.api_call(
            "im.open",
            user=dialog_submission_body['user']['id'])

        if not im_channel["ok"]:
            self.logger.error(
                "Can't open im channel for: " + str(dialog_submission_body['user']['id']) + '. ' + im_channel["error"])

        resp = self.slack_client.api_call(
            "chat.postMessage",
            channel=im_channel['channel']['id'],
            attachments=details,
            as_user=True
        )

        if not resp["ok"]:
            self.logger.error("Can't post message: " + resp.get("error"))

        return None, 204

    def list_command_message(self, command_body, user):
        message_text = "I'm going to list saved time records..."

        inner_user_id = self.extract_slack_user_id(user)
        if inner_user_id is not None:
            slack_inner_user_details = self.slack_client.api_call(
                "users.info",
                user=inner_user_id
            )

            if not slack_inner_user_details['ok']:
                return {
                           "text": "Can't fetch slack user info"
                       }, 200
            message_text = "I'm going to list saved time records for *" + slack_inner_user_details['user'][
                'real_name'] + "*..."

        message = {
            "text": message_text,
            "response_type": "ephemeral",
            'mrkdwn': True,
            "attachments": [
                {
                    "text": "Show record for",
                    "fallback": "Select time range to list saved time records",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "callback_id": CALLBACK_TOKEN_LIST_COMMAND_TIME_RANGE,
                    "actions": [
                        {
                            "name": inner_user_id if inner_user_id is not None else command_body['user_id'],
                            "text": "Select time range...",
                            "type": "select",
                            "options": [{'text': o.value, 'value': o.value} for o in TimeRanges]
                        }
                    ],
                }
            ]
        }

        return message, 200

    def list_command_time_range_selected(self, message_response_body):
        inner_user_id = message_response_body['actions'][0]['name']
        if inner_user_id != message_response_body['user']['id']:
            slack_user_details = self.slack_client.api_call(
                "users.info",
                user=message_response_body['user']['id']
            )

            if not slack_user_details['ok']:
                return {
                           "text": "Can't fetch slack user info"
                       }, 200

            user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                        slack_user_details['user']['profile']['real_name_normalized'],
                                        slack_user_details['user']['is_owner'])
            if user.role.role != 'admin':
                return {
                           "text": "Sorry, but only admin user can see other users records :face_with_monocle:"
                       }, 200

        user = self.get_user_by_slack_user_id(inner_user_id)

        if user is None:
            message = {
                "text": "It looks like, no records have been submitted yet :confused:",
                "response_type": "ephemeral",
            }
            return message, 200

        time_range_selected = message_response_body['actions'][0]['selected_options'][0]['value']

        start_end = SlackCommandService.get_start_end_date(time_range_selected)

        time_records = self.user_service.get_user_time_entries(user.user_id, start_end[0], start_end[1])

        if len(time_records) == 0:
            return {
                       "text": "There is no time entries for `" + time_range_selected + "`",
                       "response_type": "ephemeral",
                   }, 200

        projects = {}
        for time in time_records:
            if projects.get(time.project.name):
                projects[time.project.name]["text"] += "\n" + self.make_time_string(time)
            else:
                projects[time.project.name] = {
                    "title": time.project.name,
                    "text": self.make_time_string(time),
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "mrkdwn_in": ["text"]
                }

        if inner_user_id == message_response_body['user']['id']:
            projects['footer'] = {
                "text": "",
                "footer": "Use */ni delete* to remove record",
                "mrkdwn_in": ["footer"]
            }

        message = {
            "text": "These are hours submitted by *" + ("You" if inner_user_id == message_response_body['user'][
                'id'] else user.first_name) + "* for `" + time_range_selected + "`",
            "mrkdwn": True,
            "response_type": "ephemeral",
            "attachments": list(projects.values())
        }

        return message, 200

    def report_dialog(self, command_body):
        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        project_options_list = [{'label': p.name, 'value': p.project_id} for p in projects]

        # todo select default project for current user
        default_project = project_options_list[0]

        today = date.today().isoformat()
        previous_week = (date.today() - timedelta(7)).isoformat()

        slack_user_details = self.slack_client.api_call(
            "users.info",
            user=command_body['user_id']
        )

        if not slack_user_details['ok']:
            return {
                       "errors": [
                           {
                               "name": "user",
                               "error": "No such user !"
                           }
                       ]
                   }, 200

        dialog = {
            "title": "Generate report",
            "submit_label": "Generate",
            "callback_id": CALLBACK_TOKEN_REPORT_SUBMIT,
            "elements": [
                {
                    "label": "Project",
                    "type": "select",
                    "name": "project",
                    "placeholder": "Select a project",
                    "value": default_project['value'],
                    "options": project_options_list
                },
                {
                    "label": "Date from",
                    "type": "text",
                    "name": "day_from",
                    "placeholder": "Specify date",
                    "value": previous_week
                },
                {
                    "label": "Date to",
                    "type": "text",
                    "name": "day_to",
                    "placeholder": "Specify date",
                    "value": today
                }
            ]
        }

        # admin see users list
        user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                    slack_user_details['user']['profile']['real_name_normalized'],
                                    slack_user_details['user']['is_owner'])
        if user.role.role == 'admin':
            users = self.user_service.get_users()
            user_options_list = [{'label': str(p.first_name), 'value': p.user_id} for p in
                                 users]
            dialog['elements'].append({
                "label": "User",
                "type": "select",
                "name": "user",
                "placeholder": "Select user",
                "optional": "true",
                "options": user_options_list
            })

        resp = self.slack_client.api_call(
            "dialog.open",
            trigger_id=command_body['trigger_id'],
            dialog=dialog
        )

        if not resp["ok"]:
            self.app.logger.error("Can't open report dialog: " + resp.get("error"))

        return None, 204

    def report_generate_command(self, command_body):
        date_to = command_body['submission']['day_to']
        date_from = command_body['submission']['day_from']

        if 'user' in command_body['submission']:
            selected_user = command_body['submission']['user']
        else:
            selected_user = None
        project_id = command_body['submission']['project']

        print_param = PrintParameters()
        print_param.date_to = date_to
        print_param.date_from = date_from
        print_param.project_id = project_id

        if not validate_date(print_param.date_to):
            return {
                       "errors": [
                           {
                               "name": "date_from",
                               "error": "Provide date in format year-month-day, e.g. " + date.today().isoformat()
                           }
                       ]
                   }, 200

        if not validate_date(print_param.date_from):
            return {
                       "errors": [
                           {
                               "name": "date_to",
                               "error": "Provide date in format year-month-day, e.g. " + date.today().isoformat()
                           }
                       ]
                   }, 200

        # todo cache projects globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == print_param.project_id, projects)

        if selected_project is None:
            return {
                       "errors": [
                           {
                               "name": "project",
                               "error": "Project doesn't exist"
                           }
                       ]
                   }, 200

        slack_user_details = self.slack_client.api_call(
            "users.info",
            user=command_body['user']['id']
        )

        if not slack_user_details['ok']:
            return {
                       "errors": [
                           {
                               "name": "user",
                               "error": "Cannot generate report for current user"
                           }
                       ]
                   }, 200

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

        im_channel = self.slack_client.api_call(
            "im.open",
            user=command_body['user']['id'])

        if not im_channel["ok"]:
            self.logger.error(
                "Can't open im channel for: " + str(selected_user) + '. ' + im_channel["error"])

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
            self.app.logger.error("Cannot delete report file{0}".format(err))

        if not resp["ok"]:
            self.app.logger.error("Can't send report: " + resp.get("error"))

        return None, 204

    def reminder_show(self, command_body):
        command_name = command_body["command"]
        slack_user_details = self.slack_client.api_call(
            "users.info",
            user=command_body['user_id']
        )

        if not slack_user_details['ok']:
            return {
                       "errors": [
                           {
                               "name": "user",
                               "error": "No such user !"
                           }
                       ]
                   }, 200
        user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                    slack_user_details['user']['profile']['real_name_normalized'],
                                    slack_user_details['user']['is_owner'])
        day_configuration = self.reminder_service.get_user_reminder_config(user)

        attachment = [
            {"text": day_time, "color": "#D72B3F" if "OFF" in day_time else "#3AA3E3", "attachment_type": "default",
             "mrkdwn_in": ["text"]} for day_time in day_configuration]
        attachment.append({
            "text": "",
            "footer": "Use *{0} reminder set mon:hh:mm,wed:off* to change settings".format(command_name),
            "mrkdwn_in": [
                "text",
                "footer"
            ]
        }
        )
        return {
                   'text': "Your reminder time is as follow:",
                   'mrkdwn': True,
                   "attachments": attachment

               }, 200

    def reminder_set(self, command_body):
        slack_user_details = self.slack_client.api_call(
            "users.info",
            user=command_body['user_id']
        )

        if not slack_user_details['ok']:
            return {
                       "errors": [
                           {
                               "name": "user",
                               "error": "No such user !"
                           }
                       ]
                   }, 200

        user = self.get_or_add_user(slack_user_details['user']['profile']['email'],
                                    slack_user_details['user']['profile']['real_name_normalized'],
                                    slack_user_details['user']['is_owner'])

        index = command_body['text'].find('set') + len('set ')

        if self.reminder_service.set_user_reminder_config(user, command_body['text'][index:]):
            return "Remind times set", 200
        else:
            return {
                       "errors": [
                           {
                               "name": "time",
                               "error": "incorrect format. Examples: /reminder set 15:15 /reminder set "
                                        "mon:15:15;tue:13:14;sat:18:10 "
                           }
                       ]
                   }, 200

    def delete_command_message(self, command_body):
        project_options_list = self.get_projects_option_list()
        user_default_project = self.get_default_project_for_user(project_options_list,
                                                                 self.get_user_by_slack_user_id(
                                                                     command_body['user_id']))

        message = {
            "text": "I'm going to remove time entry :wastebasket:...",
            "response_type": "ephemeral",
            "attachments": [
                {
                    "text": "Select project first",
                    "fallback": "Select project",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "callback_id": CALLBACK_TOKEN_DELETE_COMMAND_PROJECT,
                    "actions": [
                        {
                            "name": "projects_list",
                            "text": "Select project...",
                            "type": "select",
                            "value": user_default_project['value'],
                            "options": [{'text': p['label'], 'value': p['value']} for p in project_options_list]
                        }
                    ]
                }
            ]
        }

        return message, 200

    def delete_command_project_selected(self, message_response_body):
        project_id_selected = message_response_body['actions'][0]['selected_options'][0]['value']

        projects = self.project_service.get_projects()
        selected_project = list_find(lambda p: str(p.project_id) == project_id_selected, projects)

        user = self.get_user_by_slack_user_id(message_response_body['user']['id'])

        if user is None:
            message = {
                "text": "You didn't submit any hours yet :face_with_raised_eyebrow:",
                "response_type": "ephemeral",
            }
            return message, 200

        last_time_entries = self.user_service.get_last_ten_time_entries(user.user_id, selected_project.project_id)

        if len(last_time_entries) == 0:
            return {
                       "text": "Can't find any time entries for *" + selected_project.name + "* :face_with_rolling_eyes:",
                       "response_type": "ephemeral",
                       "mrkdwn": True
                   }, 200

        message = {
            "text": "There are the last time entries for *" + selected_project.name + "*:",
            "response_type": "ephemeral",
            "mrkdwn": True,
            "attachments": [
                {
                    "text": "Select time entry to remove",
                    "fallback": "Select time entry",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "callback_id": CALLBACK_TOKEN_DELETE_COMMAND_TIME_ENTRY,
                    "actions": [
                        {
                            "name": "time_entries_list",
                            "text": "Select time entry...",
                            "type": "select",
                            "options": [
                                {'text': SlackCommandService.make_option_time_string(t), 'value': t.time_entry_id}
                                for
                                t in last_time_entries]
                        }
                    ]
                }
            ]
        }

        return message, 200

    def delete_command_time_entry_selected(self, message_response_body):
        time_entry_id_selected = message_response_body['actions'][0]['selected_options'][0]['value']

        user = self.get_user_by_slack_user_id(message_response_body['user']['id'])
        time_entry = self.user_service.get_time_entry(user.user_id, time_entry_id_selected)

        message = {
            "text": "Time entry will be removed...",
            "response_type": "ephemeral",
            "mrkdwn": True,
            "attachments": [
                {
                    "text": "Click 'Remove' to confirm:",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "callback_id": CALLBACK_TOKEN_DELETE_COMMAND_CONFIRM,
                    "actions": [
                        {
                            "name": "remove",
                            "text": "Remove",
                            "style": "danger",
                            "type": "button",
                            "value": time_entry.time_entry_id,
                        },
                        {
                            "name": "cancel",
                            "text": "Cancel",
                            "type": "button",
                            "value": "remove",
                        }
                    ]
                }
            ]
        }

        return message, 200

    def delete_command_time_entry_confirm_remove(self, message_response_body):
        action_selected = message_response_body['actions'][0]
        if action_selected['name'] == 'remove':
            user = self.get_user_by_slack_user_id(message_response_body['user']['id'])
            self.user_service.delete_time_entry(user.user_id, int(action_selected['value']))

            return {
                       "text": "Time entry removed! :wink:",
                       "response_type": "ephemeral",
                   }, 200

        return {
                   "text": "Canceled :wink:",
                   "response_type": "ephemeral",
               }, 200

    def submit_time_dialog_reminder(self, submission_body):
        project_options_list = self.get_projects_option_list()
        user_default_project = self.get_default_project_for_user(project_options_list,
                                                                 self.get_user_by_slack_user_id(
                                                                     submission_body['user']['id']))

        today = date.today().isoformat()

        dialog = {
            "title": "Submitting time",
            "submit_label": "Submit",
            "callback_id": CALLBACK_TOKEN_TIME_SUBMIT,
            "elements": [
                {
                    "label": "Project",
                    "type": "select",
                    "name": "project",
                    "placeholder": "Select a project",
                    "value": user_default_project['value'],
                    "options": project_options_list
                },
                {
                    "label": "Day",
                    "type": "text",
                    "name": "day",
                    "placeholder": "Specify date",
                    "value": today
                },
                {
                    "label": "Duration",
                    "name": "duration",
                    "type": "text",
                    "subtype": "number",
                    "placeholder": "Hours"
                },
                {
                    "label": "Note",
                    "name": "comment",
                    "type": "textarea",
                    "hint": "Provide short description"
                }
            ]
        }

        resp = self.slack_client.api_call(
            "dialog.open",
            trigger_id=submission_body['trigger_id'],
            dialog=dialog
        )

        if not resp["ok"]:
            self.logger.error("Can't open dialog submit time: " + resp.get("error"))

        im_channel = self.slack_client.api_call(
            "im.open",
            user=submission_body['user']['id'])

        if not im_channel["ok"]:
            self.logger.error(
                "Can't open im channel for: " + str(submission_body['user']['id']) + '. ' + im_channel["error"])

        resp = self.slack_client.api_call(
            "chat.delete",
            channel=im_channel['channel']['id'],
            ts=submission_body['message_ts'],
            as_user=True
        )

        if not resp["ok"]:
            self.logger.error("Can't delete message: " + resp.get("error"))

        return None, 204

    @staticmethod
    def get_start_end_date(time_range_selected):
        now = dt.now()

        if time_range_selected == TimeRanges.yesterday.value:
            start = end = now.date() - timedelta(1)
        elif time_range_selected == TimeRanges.this_week.value:
            start = now.date() - timedelta(days=now.date().weekday())
            end = start + timedelta(6)
        elif time_range_selected == TimeRanges.previous_week.value:
            start = now.date() - timedelta(days=now.date().weekday() + 7)
            end = start + timedelta(6)
        elif time_range_selected == TimeRanges.this_month.value:
            start = dt(now.year, now.month, 1).date()
            end = dt(now.year, now.month, monthrange(now.year, now.month)[1]).date()
        elif time_range_selected == TimeRanges.previous_month.value:
            prev_month = 12 if now.month == 1 else now.month - 1
            year = now.year - 1 if now.month == 1 else now.year
            start = dt(year, prev_month, 1).date()
            end = dt(year, prev_month, monthrange(year, prev_month)[1]).date()
        else:
            start = end = now.date()

        return start, end

    @staticmethod
    def make_time_string(time_entry):
        return SlackCommandService.format_slack_date(time_entry.report_date) + \
               " *" + str(round(time_entry.duration, 2)) + "h*  _" + \
               (time_entry.comment[:30] + "..." if len(time_entry.comment) > 30 else time_entry.comment) + "_"

    @staticmethod
    def make_option_time_string(time_entry):
        return time_entry.report_date.strftime("%Y-%m-%d") + \
               " " + str(round(time_entry.duration, 2)) + "h " + \
               (time_entry.comment[:30] + "..." if len(time_entry.comment) > 15 else time_entry.comment)

    @staticmethod
    def format_slack_date(date_to_format):
        return "<!date^" + str(
            dt.combine(date_to_format, dt.min.time()).timestamp()).rstrip('0').rstrip(
            '.') + \
               "^{date_short}|" + date_to_format.strftime("%Y-%m-%d") + ">"

    def get_projects_option_list(self):
        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        return [{'label': p.name, 'value': p.project_id} for p in projects]

    def get_user_by_slack_user_id(self, slack_user_id):
        slack_user_details = self.slack_client.api_call(
            "users.info",
            user=slack_user_id
        )

        if not slack_user_details['ok']:
            self.logger.error("Can't get user details. Error: " + slack_user_details.get("error"))
            raise ValueError('Retrieve slack user detail failed, user_id: ' + slack_user_id)

        return self.user_service.get_user_by_email(slack_user_details['user']['profile']['email'])

    def get_default_project_for_user(self, projects_option_list, user):
        if user is not None:
            user_last_time_entry = self.user_service.get_user_last_time_entry(user.user_id)
            if user_last_time_entry is not None:
                return {'label': user_last_time_entry.project.name, 'value': user_last_time_entry.project.project_id}

        return projects_option_list[0]

    def help_command_message(self, command_body):
        command_name = command_body["command"]
        return {
                   "text": "*Nisse* is used for reporting working time.\n Available following commands:",
                   "mrkdwn": True,
                   "attachments": [
                       {
                           "text": "*{0}* _(without any arguments)_: Submit working time".format(command_name),
                           "attachment_type": "default",
                           "mrkdwn_in": [
                               "text"
                           ]
                       },
                       {
                           "text": "*{0} list*: See reported time".format(command_name),
                           "attachment_type": "default",
                           "mrkdwn_in": [
                               "text"
                           ]
                       },
                       {
                           "text": "*{0} delete*: Remove reported time".format(command_name),
                           "attachment_type": "default",
                           "mrkdwn_in": [
                               "text"
                           ]
                       },
                       {
                           "text": "*{0} reminder*: See reminder settings".format(command_name),
                           "attachment_type": "default",
                           "mrkdwn_in": [
                               "text"
                           ]
                       },
                       {
                           "text": "*{0} report*: Generate report file".format(command_name),
                           "attachment_type": "default",
                           "mrkdwn_in": [
                               "text"
                           ]
                       },
                       {
                           "text": "*{0} reminder set [_mon:HH:MM,tue:HH:MM..._]*: Configure reminder time for particular day, or several days at once".format(command_name),
                           "attachment_type": "default",
                           "mrkdwn_in": [
                               "text"
                           ]
                       }
                   ]
               }, 200

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


class TimeRanges(Enum):
    today = 'Today'
    yesterday = 'Yesterday'
    this_week = 'This week'
    previous_week = 'Previous week'
    this_month = 'This month'
    previous_month = 'Previous month'


class TimeRecord(NamedTuple):
    day: str
    duration: float
    comment: str
    project: str

    def get_parsed_date(self):
        return datetime.datetime.strptime(self.day, '%Y-%m-%d').date()
