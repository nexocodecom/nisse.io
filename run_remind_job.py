import logging
from flask import Flask
from nisse.services.reminder_job import remind
from nisse.utils.configs import load_config
from nisse.utils.logging import init_logging

application = Flask(__name__, instance_relative_config=True)

load_config(application)
init_logging(application)

remind(application.logger, application.config)