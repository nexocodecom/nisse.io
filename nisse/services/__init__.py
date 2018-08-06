import logging

from flask import Flask
from flask_injector import Binder
from flask_injector import request
from flask_sqlalchemy import SQLAlchemy
from injector import singleton
from slackclient import SlackClient
from sqlalchemy.orm import Session

from nisse.models import Base
from nisse.services.client_service import ClientService
from nisse.services.project_api_service import ProjectApiService, _get_workday_date_n_days_ago
from nisse.services.project_service import ProjectService
from nisse.services.reminder_service import ReminderService
from nisse.services.slack.slack_command_service import SlackCommandService
from nisse.services.token_service import TokenService
from nisse.services.user_service import UserService
from nisse.services.user_service import UserService


def configure_container(binder: Binder):

    binder.bind(logging.Logger, to=binder.injector.get(Flask).logger)

    binder.bind(SQLAlchemy, to=SQLAlchemy(binder.injector.get(Flask), model_class=Base), scope=singleton)

    binder.bind(Session, to=binder.injector.get(SQLAlchemy).session, scope=request)

    binder.bind(ProjectService, scope=request)

    binder.bind(ProjectApiService, scope=request)

    binder.bind(ClientService, scope=request)

    binder.bind(UserService, scope=request)

    binder.bind(TokenService, scope=request)

    binder.bind(SlackClient, to=SlackClient(binder.injector.get(Flask).config['SLACK_BOT_ACCESS_TOKEN']))

    binder.bind(SlackCommandService, scope=request)

    binder.bind(ReminderService, to=ReminderService(binder.injector.get(UserService),
                                                    binder.injector.get(logging.Logger),
                                                    binder.injector.get(Flask).config['USERS_TIME_ZONE']))

