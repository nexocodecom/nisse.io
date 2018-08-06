import os
import logging
from cmreslogging.handlers import CMRESHandler

def init_logging(application):

    env_name = 'development'
    if 'APP_CONFIG_FILE' in os.environ:
        env_name = os.environ['APP_CONFIG_FILE']

    handler = CMRESHandler(hosts=[{'host': 'srv-2.nexo.zone', 'port': 9200}],
                       auth_type=CMRESHandler.AuthType.NO_AUTH,
                       es_index_name="logs-nisse",
                       es_additional_fields={'environment': env_name})

    application.logger.setLevel(logging.DEBUG)
    application.logger.addHandler(handler)
