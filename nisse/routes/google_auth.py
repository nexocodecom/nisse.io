from flask_restful import Resource, request
from flask_injector import inject
import google.oauth2.credentials
import google_auth_oauthlib.flow
import flask
import requests
import requests_oauthlib
from nisse.services import OAuthStore

SCOPES = ['https://www.googleapis.com/auth/calendar',
          'https://www.googleapis.com/auth/calendar']

def get_flow(state=None):
    return google_auth_oauthlib.flow.Flow.from_client_secrets_file("./config/client_secret.json", scopes=SCOPES, state=state)
    
def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

@inject
def google_authorize(store: OAuthStore):    
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = get_flow()
    # The URI created here must exactly match one of the authorized redirect URIs
    # for the OAuth 2.0 client, which you configured in the API Console. If this
    # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
    # error.
    flow.redirect_uri = flask.url_for('nisseoauthcallback', _external=True)
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')
    # Store the state so the callback can verify the auth server response.
    store.set_state(state)
    return flask.redirect(authorization_url)

@inject
def google_nisseoauthcallback(store: OAuthStore):
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = store.get_state()
    flow = get_flow(state=state)
    flow.redirect_uri = flask.url_for('nisseoauthcallback', _external=True)
    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)
    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    store.set_credentials(flow.credentials)
    return ("OK", 200)

@inject
def google_revoke(store: OAuthStore):
    credentials = store.get_credentials()
    revoke = requests.post('https://accounts.google.com/o/oauth2/revoke',
                           params={'token': credentials.token},
                           headers={'content-type': 'application/x-www-form-urlencoded'})
    status_code = getattr(revoke, 'status_code')
    store.clear_credentials()
    return status_code
