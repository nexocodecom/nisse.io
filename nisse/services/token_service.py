from flask_injector import inject
from nisse.models.database import Token
from datetime import datetime, timedelta
from sqlalchemy.orm import Session


class TokenService(object):
    """
    Handles tokens - used in Password Grant Type
    """
    @inject
    def __init__(self, session: Session):
        self.db = session()

    def find(self, client_id:str) -> Token:
        """ Retrieve a token record using submitted access token or
        refresh token.

        :param access_token: User access token.
        :param refresh_token: User refresh token.
        """        
        return self.db.query(Token) \
            .filter(client_id == Token.client_id).first()

    def save(self, token):
        """ Save a new token to the database.

        :param token: Token dictionary containing access and refresh tokens,
            plus token type.
        :param request: Request dictionary containing information about the
            client and user.
        """
        db_token = self.find(token['client_id'])

        if db_token:
            db_token.token = token['token']
            db_token.refresh_token = token['refresh_token'] or db_token.refresh_token
            db_token.token_uri = token['token_uri'] or db_token.token_uri
            db_token.client_secret = token['client_secret'] or db_token.client_secret
        else:
            scopes = token.pop('scopes', None)
            token['scopes'] = ';'.join(scopes) if scopes else ''
            db_token = Token(**token)            
            self.db.add(db_token)
        
        self.db.commit()

    def __del__(self):
        if self.db is not None:
            self.db.close()
