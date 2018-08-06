import logging
from flask import Flask
from nisse.services.reminder_job import remind
from nisse.utils.load_config import load_config

application = Flask(__name__, instance_relative_config=True)
application.logger.setLevel(logging.DEBUG)

load_config(application)

remind(application.logger, application.config)