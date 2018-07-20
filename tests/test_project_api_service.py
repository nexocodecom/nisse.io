from nisse.services import ProjectApiService, _get_workday_date_n_days_ago
from werkzeug.exceptions import BadRequest
from nisse.models.database import Project, User, UserProject
from datetime import datetime
import unittest
import mock


class ProjectApiServiceTests(unittest.TestCase):

    @mock.patch('nisse.services.ProjectService')
    @mock.patch('nisse.services.UserService')
    def setUp(self, mock_project_service, mock_user_service):
        self.mock_user_service = mock_user_service
        self.mock_project_service = mock_project_service

        self.mock_project_service.get_project_by_id.return_value = None
        self.mock_user_service.get_user_by_id.return_value = None

        self.api_service = ProjectApiService(
            mock_project_service, mock_user_service)

    def test_get_project_by_id_should_raise_badrequest_due_to_no_project(self):
        # Arrange

        # Act Assert
        with(self.assertRaises(BadRequest, msg='Project does not exist')):
            self.api_service.get_project_by_id(1)

    def test_get_project_by_id_should_get_project(self):
        # Arrange
        project = Project()
        self.mock_project_service.get_project_by_id.return_value = project

        # Act
        result = self.api_service.get_project_by_id(1)

        # Assert
        self.assertEqual(project, result)

    def test_update_project_should_change_name(self):
        # Arrange
        project = Project()
        project.name = 'old-name'

        self.mock_project_service.get_project_by_id.return_value = project

        # Act
        updated_project = self.api_service.update_project(1, 'new-name')

        # Assert
        self.assertEqual(updated_project['project_name'], 'new-name')

    def test_update_project_should_raise_badrequest_due_to_no_project(self):
        # Arrange

        # Act
        with self.assertRaises(BadRequest, msg='Project does not exist'):
            self.api_service.update_project(1, 'new-name')

    def test_delete_project_should_delete(self):
        # Arrange
        project = Project()
        self.mock_project_service.get_project_by_id.return_value = project

        # Act
        self.api_service.delete_project(1)

        # Assert
        self.mock_project_service.delete_project.assert_called_once_with(
            project)

    def test_delete_project_should_raise_badrequest(self):
        # Arrange

        # Act
        with self.assertRaises(BadRequest, msg='Project does not exist'):
            self.api_service.delete_project(1)

    def test_create_project_should_create(self):
        # Arrange
        project = Project()
        project.name = 'project'
        self.mock_project_service.create_project.return_value = project

        # Act
        result = self.api_service.create_project('project')

        # Assert
        self.mock_project_service.create_project.assert_called_once_with(
            'project')
        self.assertEqual(result['project_name'], 'project')

    def test_assign_user_to_project_should_raise_badrequest_due_to_no_project(self):
        # Arrange

        # Act & Assert
        with(self.assertRaises(BadRequest, msg='Project does not exist')):
            self.api_service.assign_user_to_project(1, 1)

    def test_assign_user_to_project_should_raise_badrequest_due_to_no_user(self):
        # Arrange
        self.mock_project_service.get_project_by_id.return_value = Project()

        # Act & Assert
        with(self.assertRaises(BadRequest, msg='User does not exist')):
            self.api_service.assign_user_to_project(1, 1)

    @mock.patch('nisse.models.database.Project')
    def test_assign_user_to_project_should_raise_badrequest_due_to_user_assigned(self, mock_project):
        # Arrange
        mock_project.project_users.filter().first.return_value = UserProject()

        user = User()
        self.mock_project_service.get_project_by_id.return_value = mock_project
        self.mock_user_service.get_user_by_id.return_value = user

        # Act & Assert
        with self.assertRaises(BadRequest, msg='User already assigned to project'):
            self.api_service.assign_user_to_project(1, 1)

    @mock.patch('nisse.models.database.Project')
    def test_assign_user_should_assign_user_to_project(self, mock_project):
        # Arrange
        mock_project.project_users.filter().first.return_value = None
        user = User()
        self.mock_project_service.get_project_by_id.return_value = mock_project
        self.mock_user_service.get_user_by_id.return_value = user

        # Act
        self.api_service.assign_user_to_project(1, 1)

        # Assert
        self.mock_project_service.assign_user_to_project.assert_called_once_with(
            mock_project, user)

    def test_report_user_time_should_raise_badrequest_dueto_no_user(self):
        # Arrange

        # Act & Assert
        with self.assertRaises(BadRequest, msg='User does not exist'):
            self.api_service.report_user_time(1, 1, 10, 'comment', datetime.now())

    def test_report_user_time_should_raise_badrequest_dueto_no_project(self):
        # Arrange
        self.mock_user_service.get_user_by_id.return_value = User()

        # Act & Assert
        with self.assertRaises(BadRequest, msg='Project does not exist'):
            self.api_service.report_user_time(1, 1, 1, 'comment', datetime.now())

    def test__get_workday_date_n_days_ago(self):
        monday = datetime(2018, 6, 11)
        result = _get_workday_date_n_days_ago(2, monday)
        prev_week_thursday = datetime(2018, 6, 7).date()
        self.assertEqual(prev_week_thursday, result)

        tuesday = datetime(2018, 6, 12)
        result = _get_workday_date_n_days_ago(2, tuesday)
        prev_week_friday = datetime(2018, 6, 8).date()
        self.assertEqual(prev_week_friday, result)

        
    @mock.patch('nisse.models.database.Project')
    @mock.patch('nisse.models.database.User')
    @mock.patch('nisse.models.database.UserProject')
    def test_report_user_time_should_raise_badrequest_dueto_too_much_time_reported(self, mock_project, mock_user, mock_user_project):
        # Arrange
        mock_user.user_time_entries.filter().sum.return_value = 8*60
        mock_user_project.user = mock_user
        mock_project.project_users.filter().first.return_value = mock_user_project
        self.mock_project_service.get_project_by_id.return_value = mock_project
        seconds_reported = 60*30

        expectedMsg = 'Could not perfom time report due to exceeded maximum limit of reported time amount. Reported time: 0:30:00. ' +\
                      'Currently reported total time: 8:00:00. '+\
                      'Maximum time amount to report: 8:00:00, limit exceeded by: 00:30:00.'

        # Act & Assert
        with self.assertRaises(BadRequest, msg = expectedMsg):
            self.api_service.report_user_time(1, 1, seconds_reported, datetime.now(), 'comment')

