from google.oauth2.credentials import Credentials
import json
import os.path

class OAuthStore(object):
    def __init__(self):
        self.credentials = None
        self.state = None

    def set_credentials(self, credentials: Credentials):
        with open('creds.json', 'w') as outfile:
            json.dump(self.credentials_to_dict(credentials), outfile)            
        self.credentials = credentials

    def get_credentials(self) -> Credentials:
        if self.credentials is None and os.path.isfile('creds.json'):            
            with open('creds.json', 'r') as infile:
                self.credentials = self.credentials_from_dict(json.loads(infile.read()))
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

    def credentials_to_dict(self, credentials):
        return {'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes}

    def credentials_from_dict(self, credentials):
        return Credentials(**credentials)