from flask_sqlalchemy import SQLAlchemy
from flask_injector import inject
from nisse.models.database import Project, User, UserProject, TimeEntry
import datetime


class ProjectService(object):
    """ Project service
    """
    @inject
    def __init__(self, db: SQLAlchemy):
        self.db = db

    def get_projects(self):
        return self.db.session.query(Project) \
            .all()

    def get_projects_by_user(self, user_id: int):
        return self.db.session.query(Project) \
            .join(UserProject.project) \
            .filter(UserProject.user_id == user_id) \
            .all()

    def create_project(self, project_name):
        new_project = Project(name=project_name)
        self.db.session.add(new_project)
        self.db.session.commit()
        return new_project

    def get_project_by_id(self, project_id: int):
        return self.db.session.query(Project) \
            .filter(project_id == Project
                    .project_id).first()

    def update_project(self, project: Project):
        self.db.session.commit()

    def delete_project(self, project: Project):
        self.db.session.delete(project)
        self.db.session.commit()

    def assign_user_to_project(self, project: Project, user: User):
        user_project = UserProject(
            project_id=project.project_id, user_id=user.user_id)
        self.db.session.add(user_project)
        self.db.session.commit()

    def report_user_time(self, project: Project, user: User, duration: float, comment: str, report_date: datetime):
        time_entry = TimeEntry(user_id=user.user_id,
                               project_id=project.project_id,
                               duration=duration,
                               comment=comment,
                               report_date=report_date
                               )
        self.db.session.add(time_entry)
        self.db.session.commit()
        return time_entry
