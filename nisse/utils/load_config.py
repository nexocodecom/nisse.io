import os
import logging
from logging.handlers import RotatingFileHandler

def load_config(application):

    # load specific configuration file by environment if specified, otherwise load development config.
    if 'APP_CONFIG_FILE' in os.environ:
        application.logger.warning('Detected configured APP_CONFIG_FILE: ' +
                                   os.environ['APP_CONFIG_FILE'])
        application.config.from_object('config.' + os.environ['APP_CONFIG_FILE'])

        if os.environ['APP_CONFIG_FILE'] != 'local':
            file_logger_handler = RotatingFileHandler(filename=application.config["LOGS_PATH"], mode='a', maxBytes=5000000,
                                                      backupCount=10)
            file_logger_handler.setLevel(logging.DEBUG)
            file_logger_handler.setFormatter(logging.Formatter(
                '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
            ))
            application.logger.addHandler(file_logger_handler)
    else:
        application.logger.warning(
            'No APP_CONFIG_FILE variable configured, loading development settings')
        application.config.from_object('config.development')

    # load instance specific configuration from /instance/config.py file.
    application.config.from_pyfile('config.py')