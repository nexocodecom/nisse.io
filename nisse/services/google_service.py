from google.oauth2 import id_token
from google.auth.transport import requests
from functools import wraps
from flask import request, abort
from flask import current_app


def login_required(f):
    """Verifies ID Token issued by Google's OAuth 2.0 authorization server.
        Token Id should be send in authorization header


        Usage example:

            @app.route("/authorizedPath")
            @login_required
            def method_test():
                return 'user is authorized'
        """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'Authorization' not in request.headers:
            # Unauthorized
            abort(401)
            return None
        header = request.headers['Authorization']
        google_token = header.split(" ")[1]

        try:
            validate_token(google_token, current_app.config['GOOGLE_API_CLIENT_ID'])
        except ValueError:
            abort(401)
            return None

        return f(*args, **kwargs)
    return decorated_function


def validate_token(token, client_id):
    # Specify the CLIENT_ID of the app that accesses the backend:
    idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
    # Or, if multiple clients access the backend server:
    # idinfo = id_token.verify_oauth2_token(token, requests.Request())
    # if idinfo['aud'] not in [CLIENT_ID_1, CLIENT_ID_2, CLIENT_ID_3]:
    #     raise ValueError('Could not verify audience.')

    if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
        raise ValueError('Wrong issuer.')

    # If auth request is from a G Suite domain:
    # if idinfo['hd'] != GSUITE_DOMAIN_NAME:
    #     raise ValueError('Wrong hosted domain.')

    # ID token is valid. Get the user's Google Account ID from the decoded token.
    return idinfo
