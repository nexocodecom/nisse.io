import os
import logging
from cmreslogging.handlers import CMRESHandler

def init_logging(application):

    # if application.config['ELASTIC_HOST']:
    env_name = 'development'
    if 'APP_CONFIG_FILE' in os.environ:
        env_name = os.environ['APP_CONFIG_FILE']

    handler = CMRESHandler(hosts=[{'host': application.config.get("ELASTIC_HOST"), 'port': application.configget("ELASTIC_PORT")}],
                       auth_type=CMRESHandler.AuthType.NO_AUTH,
                       es_index_name="logs-nisse",
                       es_additional_fields={'environment': env_name})
    application.logger.addHandler(handler)

    application.logger.setLevel(logging.DEBUG)

