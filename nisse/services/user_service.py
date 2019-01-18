import datetime
import random
import string
from typing import List

from flask_bcrypt import Bcrypt
from flask_injector import inject
from sqlalchemy import and_
from sqlalchemy import exists
from sqlalchemy.orm import joinedload, Session

from nisse.models.database import User, TimeEntry, UserRole, Project, UserProject

USER_ROLE_USER = 'user'
USER_ROLE_ADMIN = 'admin'


class UserService(object):
    """
    User service
    """
    @inject
    def __init__(self, session: Session, bcrypt: Bcrypt):
        self.db = session
        self.bcrypt = bcrypt

    def find_with_password(self, username, password):
        user = self.db.query(User) \
            .filter(username == User.username) \
            .first()

        if user and password:
            if self.bcrypt.check_password_hash(user.password, password):
                return user
            else:
                return None
        else:
            return user

    def get_user_by_id(self, user_id: int):
        return self.db.query(User) \
            .filter(user_id == User.user_id) \
            .first()

    def get_user_by_email(self, email: str):
        return self.db.query(User) \
            .filter(email == User.username) \
            .first()

    def get_user_by_slack_id(self, slack_id: str):
        return self.db.query(User) \
            .filter(slack_id == User.slack_user_id) \
            .first()

    def add_user(self, username: str, first_name: str, last_name: str, password: str, slack_user_id: str, role_name=USER_ROLE_USER):
        """ Create a new User record with the supplied params

        :param username: Username of the user, email address.
        :param first_name: User first name .
        :param password: Password of the user.
        :param role_name: User role, default ='user'
        """
        role_object = self.db.query(UserRole).filter(role_name == UserRole.role).first()

        pass_hash = self.bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, first_name=first_name, last_name=last_name, slack_user_id=slack_user_id, password=pass_hash, role_id=role_object.user_role_id)
        self.db.add(new_user)
        self.db.commit()
        return new_user

    def get_default_password(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    def get_user_time_entries(self, user_id: int, start: datetime.date, end: datetime.date):
        return self.db.query(TimeEntry) \
            .join(TimeEntry.user) \
            .filter(User.user_id == user_id, TimeEntry.report_date >= start, TimeEntry.report_date <= end) \
            .order_by(TimeEntry.report_date.desc()) \
            .all()

    def get_users(self, ):
        return self.db.query(User).all()

    def get_projects_by_user(self, user_id: int):
        return self.db.session.query(Project) \
            .join(UserProject.project) \
            .filter(UserProject.user_id == user_id) \
            .all()

    def get_users_not_assigned_for_project(self, project_id: int):
        return self.db.query(User)\
            .filter(
                ~exists().where(
                    and_(
                        UserProject.user_id == User.user_id,
                        UserProject.project_id == project_id
                    )
                )
            )\
            .all()

    def get_users_assigned_for_project(self, project_id: int):
        return self.db.query(User) \
            .join(UserProject.user) \
            .filter(UserProject.project_id == project_id) \
            .all()

    def get_user_last_time_entry(self, user_id: int):
        return self.db.query(TimeEntry) \
            .options(joinedload(TimeEntry.project)) \
            .join(TimeEntry.user) \
            .filter(User.user_id == user_id) \
            .order_by(TimeEntry.report_date.desc()) \
            .first()

    def get_last_ten_time_entries(self, user_id: int, project_id: int) -> List[TimeEntry]:
        return self.db.query(TimeEntry) \
            .join(TimeEntry.user) \
            .join(TimeEntry.project) \
            .filter(User.user_id == user_id) \
            .filter(Project.project_id == project_id) \
            .order_by(TimeEntry.report_date.desc()) \
            .limit(10) \
            .all()

    def get_time_entry(self, user_id: int, time_entry_id: int) -> TimeEntry:
        return self.db.query(TimeEntry) \
            .join(TimeEntry.user) \
            .filter(User.user_id == user_id) \
            .filter(TimeEntry.time_entry_id == time_entry_id) \
            .first()

    def delete_time_entry(self, user_id: int, time_entry_id: int):
        time_entry = self.get_time_entry(user_id, time_entry_id)
        self.db.delete(time_entry)
        self.db.commit()

    def update_time_entry(self, time_entry):
        time_entry = self.get_time_entry(time_entry.user_id, time_entry.time_entry_id)
        time_entry.duration = time_entry.duration
        time_entry.comment = time_entry.comment
        self.db.commit()

    def update_remind_times(self, user_times: User):
        user = self.get_user_by_email(user_times.username)
        user.remind_time_monday = user_times.remind_time_monday
        user.remind_time_tuesday = user_times.remind_time_tuesday
        user.remind_time_wednesday = user_times.remind_time_wednesday
        user.remind_time_thursday = user_times.remind_time_thursday
        user.remind_time_friday = user_times.remind_time_friday
        user.remind_time_saturday = user_times.remind_time_saturday
        user.remind_time_sunday = user_times.remind_time_sunday
        self.db.commit()

    def get_users_to_notify(self, date, day_of_week, start_time, end_time):
        user_remind_column_by_weekday = {
            0: User.remind_time_monday,
            1: User.remind_time_tuesday,
            2: User.remind_time_wednesday,
            3: User.remind_time_thursday,
            4: User.remind_time_friday,
            5: User.remind_time_saturday,
            6: User.remind_time_sunday,
        }
        return self.db.query(User) \
            .outerjoin(TimeEntry, and_(User.user_id == TimeEntry.user_id, TimeEntry.report_date == date)) \
            .filter(user_remind_column_by_weekday[day_of_week] > start_time,
                    user_remind_column_by_weekday[day_of_week] <= end_time) \
            .filter(TimeEntry.report_date == None) \
            .all()

