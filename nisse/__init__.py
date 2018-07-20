import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy
from flask_json import FlaskJSON
from flask_injector import FlaskInjector
from flask_migrate import Migrate
from nisse.models.database import Base
import nisse.services
import nisse.routes
from nisse.services.reminder_job import remind
from nisse.utils.oauth_default_provider import oauth_default_provider
from nisse.services import ClientService, UserService, TokenService
from __version__ import __version__
import atexit

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

app = Flask(__name__, instance_relative_config=True)

app.logger.setLevel(logging.DEBUG)

# load specific configuration file by environment if specified, otherwise load development config.
if 'APP_CONFIG_FILE' in os.environ:
    app.logger.warning('Detected configured APP_CONFIG_FILE: ' +
                       os.environ['APP_CONFIG_FILE'])
    app.config.from_object('config.' + os.environ['APP_CONFIG_FILE'])

    if os.environ['APP_CONFIG_FILE'] != 'local':
        file_logger_handler = RotatingFileHandler(filename=app.config["LOGS_PATH"], mode='a', maxBytes=5000000,
                                                  backupCount=10)
        file_logger_handler.setLevel(logging.DEBUG)
        file_logger_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        ))
        app.logger.addHandler(file_logger_handler)
else:
    app.logger.warning(
        'No APP_CONFIG_FILE variable configured, loading development settings')
    app.config.from_object('config.development')

# load instance specific configuration from /instance/config.py file.
app.config.from_pyfile('config.py')

FlaskJSON(app)
api = Api(app)

nisse.routes.configure_api(api)
nisse.routes.configure_url_rules(app)

# IoC config
flask_injector = FlaskInjector(
    app=app, modules=[nisse.services.configure_container])

oauth = oauth_default_provider(app, flask_injector)
nisse.routes.configure_oauth(app, oauth)

# initial create
db = flask_injector.injector.get(SQLAlchemy)
migrate = Migrate(app, db)

app.logger.info('Version: ' + __version__)


# create report path
os.makedirs(os.path.join(app.instance_path, app.config["REPORT_PATH"]), exist_ok=True)

# setup the scheduler
scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=remind,
    args=[app.logger, app.config],
    trigger=IntervalTrigger(minutes=5),
    id='daily_reminder_job',
    name='Daily reminder',
    replace_existing=True)
# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

