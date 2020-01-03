import json
import os

from flask import Flask
from flask.config import Config
from flask_injector import inject
from flask_sqlalchemy import SQLAlchemy
from google.oauth2.credentials import Credentials

from nisse.models.database import Token
from nisse.services.token_service import TokenService


#Since its singletion in our application di config, it requires internal, manual creation of
#sql db connection on demand. Requesting SqlAlchemy session from DI would cause errors when writing/reading from database.
class OAuthStore(object):

    @inject
    def __init__(self, config: Config, flask: Flask, alchemy: SQLAlchemy):
        self.credentials = None
        self.state = None
        self.config = config
        self.alchemy = alchemy

    def set_credentials(self, credentials: Credentials):
        token_service = self._create_token_service()
        creds = self.credentials_to_dict(credentials)
        token_service.save(creds)
        self.credentials = credentials

    def get_credentials(self) -> Credentials:
        if not self.credentials and os.path.isfile('./config/client_secret.json'):
            with open('./config/client_secret.json') as infile:
                client_secret_json = infile.read()
                client_id = json.loads(client_secret_json)['web']['client_id']
                token_service = self._create_token_service()
                db_token = token_service.find(client_id)
                if db_token is None:
                    raise RuntimeError("token not found for client " + client_id)
                self.credentials = self.credentials_from_dict(self._credentials_from_db_token(db_token))
        elif not os.path.isfile('./config/client_secret.json'):
            raise RuntimeError('Unable to locate client_secret.json')

        return self.credentials

    def clear(self):
        self.set_credentials(None)
        self.state = None

    def set_state(self, state):
        self.state = state

    def get_state(self):
        state = self.state
        self.state = None
        return state

    def _create_token_service(self) -> TokenService:
        session = self.alchemy.session
        return TokenService(session=session)

    def _credentials_from_db_token(self, token: Token):
        return {'token': token.token,
                'refresh_token': token.refresh_token,
                'token_uri': token.token_uri,
                'client_id': token.client_id,
                'client_secret': token.client_secret,
                'scopes': token.scopes.split(';')
        }
    

    def credentials_to_dict(self, credentials):
        return {'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes}

    def credentials_from_dict(self, credentials):
        return Credentials(**credentials)
