from flask_restful import Resource, request
from flask_injector import inject
from nisse.services import ProjectApiService


class ProjectREST(Resource):
    @inject
    def __init__(self, service: ProjectApiService):
        self.service = service

    def get(self, project_id: int):
        project = self.service.get_project_by_id(project_id)
        return project, 200

    def put(self, project_id: int):
        project_name = request.get_json()['project_name']
        updated_project = self.service.update_project(project_id, project_name)
        return updated_project, 200

    def delete(self, project_id: int):
        self.service.delete_project(project_id)
        return None, 200


class ProjectApi(Resource):
    @inject
    def __init__(self, project_service: ProjectApiService):
        self.project_service = project_service

    def post(self):
        rq_json = request.get_json()
        created_project = self.project_service.create_project(
            rq_json['project_name'])
        return created_project, 201, {'x-created-id': created_project['project_id']}

    def get(self):
        projects = self.project_service.get_projects()
        return projects, 200

    def put(self, project_id: int, user_id: int):
        self.project_service.assign_user_to_project(project_id, user_id)
        return None, 200
