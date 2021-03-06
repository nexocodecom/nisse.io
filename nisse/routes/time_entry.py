from flask_restful import Resource, request
from flask_injector import inject
from nisse.services import ProjectApiService
from nisse.utils.date_helper import get_float_duration
import datetime


class TimeEntryApi(Resource):
    @inject
    def __init__(self, project_service: ProjectApiService):
        self.project_service = project_service

    def post(self):
        rq_json = request.get_json()
        hours = rq_json['hours']
        minutes = rq_json['minutes']
        comment = rq_json['comment']
        user_id = rq_json['user_id']
        project_id = rq_json['project_id']

        created_time_entry = self.project_service.report_user_time(
            project_id, user_id, get_float_duration(hours, minutes), comment, datetime.date.now())
        return created_time_entry, 201, {'x-created-id': created_time_entry.time_entry_id}

    def get(self, project_id: int, user_id: int):
        return None, 200