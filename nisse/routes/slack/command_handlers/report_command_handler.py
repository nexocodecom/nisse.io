import logging
import os
import uuid
from typing import List

from flask import current_app
from flask.config import Config
from flask_injector import inject
from slackclient import SlackClient
from werkzeug.utils import secure_filename

from nisse.models.DTO import PrintParametersDto
from nisse.models.slack.common import ActionType
from nisse.models.slack.common import LabelSelectOption
from nisse.models.slack.dialog import Element, Dialog
from nisse.models.slack.message import Attachment, Message, Action, TextSelectOption
from nisse.models.slack.payload import ReportGenerateFormPayload
from nisse.routes.slack.command_handlers.slack_command_handler import SlackCommandHandler
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.report_service import ReportService
from nisse.services.user_service import UserService
from nisse.services.xlsx_document_service import XlsxDocumentService
from nisse.utils import string_helper
from nisse.utils.date_helper import TimeRanges
from nisse.utils.date_helper import get_start_end_date
from nisse.utils.validation_helper import list_find


class ReportCommandHandler(SlackCommandHandler):

    @inject
    def __init__(self, config: Config, logger: logging.Logger, user_service: UserService,
                 slack_client: SlackClient, project_service: ProjectService,
                 reminder_service: ReminderService, report_service: ReportService, sheet_generator: XlsxDocumentService):
        super().__init__(config, logger, user_service, slack_client, project_service, reminder_service)
        self.report_service = report_service
        self.sheet_generator = sheet_generator

    def handle(self, payload: ReportGenerateFormPayload):

        if payload.submission:
            date_to = payload.submission.day_to
            date_from = payload.submission.day_from

            selected_user_id = None
            if hasattr(payload.submission, 'user'):
                selected_user_id = payload.submission.user

            project_id = payload.submission.project

            print_param = PrintParametersDto()
            print_param.date_to = date_to
            print_param.date_from = date_from
            print_param.project_id = project_id

            # todo cache projects globally e.g. Flask-Cache
            projects = self.project_service.get_projects()
            selected_project = list_find(lambda p: str(p.project_id) == print_param.project_id, projects)

            user = self.get_user_by_slack_user_id(payload.user.id)

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
            load_data = self.report_service.load_report_data(print_param)
            self.sheet_generator.save_report(path_for_report, print_param.date_from, print_param.date_to, load_data)

            im_channel = self.slack_client.api_call("im.open", user=payload.user.id)

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
                filename=string_helper.generate_xlsx_file_name(selected_user, selected_project_name,
                                                               print_param.date_from,
                                                               print_param.date_to)
            )

            try:
                os.remove(path_for_report)
            except OSError as err:
                self.logger.error("Cannot delete report file {0}".format(err))

            if not resp["ok"]:
                self.logger.error("Can't send report: " + resp.get("error"))

        else:
            self.show_dialog({'trigger_id': payload.trigger_id}, None, next(iter(payload.actions.values())))

    def create_dialog(self, command_body, argument, action) -> Dialog:

        selected_period = None
        if action and len(action.selected_options):
            selected_period = next(iter(action.selected_options), None).value

        start_end = get_start_end_date(selected_period)

        # todo cache it globally e.g. Flask-Cache
        projects = self.project_service.get_projects()
        project_options_list: List[LabelSelectOption] = [LabelSelectOption(label=p.name, value=p.project_id) for p in
                                                         projects]

        # admin see users list
        user = self.get_user_by_slack_user_id(action.name)

        elements: Element = [
            Element(label="Date from", type="text", name='day_from', placeholder="Specify date", value=start_end[0]),
            Element(label="Date to", type="text", name='day_to', placeholder="Specify date", value=start_end[1]),
            Element(label="Project", type="select", name='project', optional='true', placeholder="Select a project",
                    options=project_options_list)
        ]

        dialog: Dialog = Dialog(title="Generate report", submit_label="Generate",
                      callback_id=string_helper.get_full_class_name(ReportGenerateFormPayload), elements=elements)

        if action.name:
            prompted_user = self.get_user_by_slack_user_id(action.name)

        if user.role.role == 'admin':
            users = self.user_service.get_users()
            user_options_list = [LabelSelectOption(label=string_helper.get_user_name(p), value=p.user_id) for p in
                                 users]
            dialog.elements.append(
                Element(label="User", value=(prompted_user.user_id if prompted_user else None),
                        optional='true', type="select", name='user', placeholder="Select user",
                        options=user_options_list))

        return dialog

    def report_pre_dialog(self, command_body, arguments, action):

        message_text = "I'm going to generate report..."
        inner_user_id = None

        if len(arguments):
            user = arguments[0]
            inner_user_id = self.extract_slack_user_id(user)

            self.get_user_by_slack_user_id(inner_user_id)

        actions = [
            Action(
                name=inner_user_id if inner_user_id is not None else command_body['user_id'],
                text="Select time range...",
                type=ActionType.SELECT.value,
                options=[TextSelectOption(text=tr.value, value=tr.value) for tr in TimeRanges]
            )
        ]

        attachments = [
            Attachment(
                text="Generate report for",
                fallback="Select time range to report",
                color="#3AA3E3",
                attachment_type="default",
                callback_id=string_helper.get_full_class_name(ReportGenerateFormPayload),
                actions=actions
            )
        ]

        return Message(
            text=message_text,
            response_type="ephemeral",
            mrkdwn=True,
            attachments=attachments
        ).dump()
