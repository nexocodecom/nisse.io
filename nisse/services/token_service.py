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

    def find(self, access_token=None, refresh_token=None):
        """ Retrieve a token record using submitted access token or
        refresh token.

        :param access_token: User access token.
        :param refresh_token: User refresh token.
        """
        if access_token:
            return self.db.query(Token) \
            .filter(access_token == Token \
            .access_token).first()
        elif refresh_token:
            return self.db.session.query(Token) \
            .filter(refresh_token == Token \
            .refresh_token).first()

    def save(self,token, request):
        """ Save a new token to the database.

        :param token: Token dictionary containing access and refresh tokens,
            plus token type.
        :param request: Request dictionary containing information about the
            client and user.
        """
        toks = self.db.query(Token)
        filter(Token.client_id == request.client.client_id, Token.user_id==request.user.user_id)

        # Make sure that there is only one grant token for every
        # (client, user) combination.
        [self.db.delete(t) for t in toks]

        expires_in = token.pop('expires_in')
        expires = datetime.utcnow() + timedelta(seconds=expires_in)

        tok = Token(
            access_token=token['access_token'],
            refresh_token=token['refresh_token'],
            token_type=token['token_type'],
            expires=expires,
            client_id=request.client.client_id,
            user_id=request.user.user_id,
        )
        self.db.add(tok)
        self.db.commit()

    def __del__(self):
        if self.db is not None:
            self.db.close()
