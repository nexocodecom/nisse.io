from flask_injector import inject
import google_auth_oauthlib.flow
import flask
import requests
from nisse.services import OAuthStore

SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_flow(state=None, token_updater=None):
    return google_auth_oauthlib.flow.Flow.from_client_secrets_file("./config/client_secret.json", scopes=SCOPES, state=state, token_updater=token_updater)


def get_request_scheme():
    if flask.request.host.startswith('localhost') or flask.request.host.startswith('127.0.0.1'):
        return flask.request.scheme

    return 'https'


@inject
def google_authorize(store: OAuthStore):
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = get_flow()
    # The URI created here must exactly match one of the authorized redirect URIs
    # for the OAuth 2.0 client, which you configured in the API Console. If this
    # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
    # error.
    flow.redirect_uri = flask.url_for('nisseoauthcallback',
                                      _external=True,
                                      _scheme=get_request_scheme())
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        prompt='consent',
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
    flow = get_flow(state=state, token_updater=store.set_credentials)
    flow.redirect_uri = flask.url_for(
        'nisseoauthcallback',
        _external=True,
        _scheme=get_request_scheme())

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.url_for(
        'nisseoauthcallback', _external=True, _scheme=get_request_scheme(), **flask.request.values)
    flow.fetch_token(authorization_response=authorization_response)
    # Store credentials.
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
