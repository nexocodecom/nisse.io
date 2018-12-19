from flask import Flask
from nisse.routes.project import *
from flask_restful import Api
from nisse.routes.project import ProjectApi, ProjectREST
from nisse.routes.time_entry import TimeEntryApi
from nisse.routes.slack.slack_command import SlackCommand
from nisse.routes.slack.slack_interactive_message import SlackDialogSubmission
from nisse.routes.google_auth import google_authorize, google_nisseoauthcallback, google_revoke


def configure_oauth(app: Flask):
    app.add_url_rule('/google/authorize', 'authorize', google_authorize)    
    app.add_url_rule('/google/nisseoauthcallback', 'nisseoauthcallback', google_nisseoauthcallback)
    app.add_url_rule('/google/revoke', 'revoke', google_revoke)    

def configure_api(api: Api):
    # Slack endpoints
    api.add_resource(SlackCommand, '/slack/command', methods=['POST'])
    api.add_resource(SlackDialogSubmission, '/slack/dialog/submission', methods=['POST'])  

    # TODO: uncomment if you want to provide rest API
    # api.add_resource(ProjectREST, '/projects/<int:project_id>',
    # endpoint="project_id", methods=['GET', 'PUT', 'DELETE']) api.add_resource(ProjectApi, '/projects',
    # endpoint='project', methods=['GET', 'POST']) api.add_resource(ProjectApi,
    # '/projects/<int:project_id>/assignuser/<int:user_id>', endpoint="assign_user", methods=['PUT'])
    # api.add_resource(TimeEntryApi, '/projects/<int:project_id>/user/<int:user_id>', endpoint="report_time",
    # methods=['PUT'])
