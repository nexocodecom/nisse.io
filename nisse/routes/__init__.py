from flask import Flask
from nisse.routes.project import *
from flask_restful import Api
from nisse.routes.project import ProjectApi, ProjectREST
from nisse.routes.time_entry import TimeEntryApi
from nisse.routes.slack.slack_command import SlackCommand
from nisse.routes.slack.slack_interactive_message import SlackDialogSubmission
from nisse.routes.token import access_token, revoke_token, oauth_test
from flask_oauthlib.provider import OAuth2Provider


def configure_oauth(app: Flask, oauth: OAuth2Provider):
    # TODO: uncomment if you want to provide Oauth2 password grand type in your API
    # app.add_url_rule('/oauth/token', view_func=oauth.token_handler(access_token), methods=['POST'])
    # app.add_url_rule('/oauth/revoke', view_func=oauth.revoke_handler(revoke_token), methods=['POST'])
    # app.add_url_rule('/oauth/test', view_func=oauth.require_oauth()(oauth_test), methods=['GET'])
    pass


def configure_url_rules(app: Flask):
    pass


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
