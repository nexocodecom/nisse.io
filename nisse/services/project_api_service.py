from werkzeug.exceptions import BadRequest
from nisse.services.project_service import ProjectService
from nisse.services.user_service import UserService
from nisse.models import Project, TimeEntry, UserProject, User
from datetime import datetime, timedelta
from flask_injector import inject


class ProjectApiService(object):
    @inject
    def __init__(self, project_service: ProjectService, user_service: UserService):
        self.project_service = project_service
        self.user_service = user_service

    def get_project_by_id(self, project_id: int):
        project = self.project_service.get_project_by_id(project_id)

        if project is None:
            _raise_project_not_exist()

        return project

    def update_project(self, project_id: int, project_name):
        project = self.project_service.get_project_by_id(project_id)

        if project is None:
            _raise_project_not_exist()

        project.name = project_name
        self.project_service.update_project(project)
        return _create_project_json(project)

    def delete_project(self, project_id: int):
        project = self.project_service.get_project_by_id(project_id)

        if project is None:
            _raise_project_not_exist()

        self.project_service.delete_project(project)

    def create_project(self, project_name):
        project = self.project_service.create_project(project_name)
        return _create_project_json(project)

    def assign_user_to_project(self, project_id: int, user_id: int):
        project = self.project_service.get_project_by_id(project_id)
        user = self.user_service.get_user_by_id(user_id)

        if (project is None):
            _raise_project_not_exist()

        if (user is None):
            _raise_user_not_exist()

        project_user = project.project_users.filter(
            user_id == UserProject.user_id).first()
        if project_user is not None:
            raise BadRequest('User already assigned to project.')

        self.project_service.assign_user_to_project(project, user)

    def get_projects(self):
        projects = self.project_service.get_projects()
        return [_create_project_json(p) for p in projects]

    def report_user_time(self, project_id: int, user_id: int, duration: float, date: datetime, comment):
        project = self.project_service.get_project_by_id(project_id)

        if project is None:
            _raise_project_not_exist()

        user_project = project.project_users.filter(
            user_id == UserProject.user_id).first()

        if user_project is None:
            user_project = UserProject(project_id=project.project_id, user_id=user_id)

        report_date = date.date()
        user = user_project.user
        duration_timedelta = timedelta(seconds=duration)

        _validate_reported_amount_of_time(
            user, duration_timedelta, report_date)
        _validate_report_date(report_date)

        time_entry = self.project_service.report_user_time(
            project, user, duration, comment)

        return _create_time_entry_json(time_entry)


def _validate_report_date(report_date: datetime):
    # Maximum days behind which could be reported or modified.
    MAX_DAYS_IN_PAST = 2

    past_work_day_day = _get_workday_date_n_days_ago(
        MAX_DAYS_IN_PAST,
        datetime.now().date())

    if (report_date < past_work_day_day):
        raise BadRequest('The time can be reported only 2 days back.')


def _validate_reported_amount_of_time(user: User, duration: timedelta, report_date: datetime):
    # Get total time amount reported by user for date
    user_reported_time = user.user_time_entries \
        .filter(report_date == TimeEntry.report_date) \
        .sum(TimeEntry.duration)

    total_user_time = timedelta(minutes=user_reported_time)

    total_user_time_including_duration = total_user_time + duration

    # Maximum hours which could be reported per user per day
    MAX_HOURS_TO_REPORT = timedelta(hours=8)

    exceeded_by = total_user_time_including_duration - MAX_HOURS_TO_REPORT

    if (total_user_time_including_duration > MAX_HOURS_TO_REPORT):
        msg = 'Could not perfom time report due to exceeded maximum limit of reported time. Reported time: ' + str(
            duration) + '. ' + \
              'Currently reported total time: ' + str(total_user_time) + '. ' + \
              'Maximum time amount to report: ' + str(MAX_HOURS_TO_REPORT) + ', limit exceeded by: ' + str(
            exceeded_by) + '.'
        raise BadRequest(msg)


def _get_workday_date_n_days_ago(days_ago: int, date: datetime):
    if (days_ago <= 0 or days_ago > 100):
        raise Exception('days_ago must be between 1 and 100')

    days_subtracted = 0
    new_date = date
    while days_subtracted < days_ago:
        new_date = new_date - timedelta(days=1)

        day_of_week = new_date.weekday()

        # 0 is monday, 6 - sunday - skip counting subtractions on weekend days.
        if (day_of_week == 5 or day_of_week == 6):
            continue

        days_subtracted += 1

    return new_date.date()


def _raise_project_not_exist():
    raise BadRequest('Project does not exist')


def _raise_user_not_exist():
    raise BadRequest('User does not exist')


def _create_project_json(project: Project):
    return {
        'project_id': project.project_id,
        'project_name': project.name
    }


def _create_time_entry_json(time_entry: TimeEntry):
    return {
        'project_id': time_entry.project.project_id,
        'project_name': time_entry.project.name,
        'user_name': time_entry.user.name,
        'user_id': time_entry.user.user_id,
        'duration': time_entry.duration,
        'comment': time_entry.comment
    }
