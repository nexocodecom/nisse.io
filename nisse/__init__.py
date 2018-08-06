import os
import logging
from flask import Flask
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy
from flask_json import FlaskJSON
from flask_injector import FlaskInjector
from flask_migrate import Migrate
from nisse.models.database import Base
import nisse.services
import nisse.routes
from nisse.utils.configs import load_config
from nisse.utils.logging import init_logging
from nisse.utils.oauth_default_provider import oauth_default_provider
from nisse.services import ClientService, UserService, TokenService
from __version__ import __version__

application = Flask(__name__, instance_relative_config=True)

load_config(application)
init_logging(application)

FlaskJSON(application)
api = Api(application)

nisse.routes.configure_api(api)
nisse.routes.configure_url_rules(application)

# IoC config
flask_injector = FlaskInjector(
    app=application, modules=[nisse.services.configure_container])

oauth = oauth_default_provider(application, flask_injector)
nisse.routes.configure_oauth(application, oauth)

# initial create
db = flask_injector.injector.get(SQLAlchemy)
migrate = Migrate(application, db)

application.logger.info('Version: ' + __version__)

# create report path
os.makedirs(os.path.join(application.instance_path, application.config["REPORT_PATH"]), exist_ok=True)