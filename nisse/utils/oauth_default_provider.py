from flask_oauthlib.provider import OAuth2Provider
from flask import Flask
from nisse.services import ClientService, UserService, TokenService
from flask_injector import FlaskInjector


def oauth_default_provider(app: Flask, flask_injector: FlaskInjector):
    """ This is password grand type provider implementation used by flask_oauthlib"""
    oauth = OAuth2Provider(app)

    @oauth.clientgetter
    def get_client(client_id):
        client_service = flask_injector.injector.get(ClientService)
        client = client_service.find(client_id)
        return client

    @oauth.grantgetter
    def get_grant(client_id, code):
        return None

    @oauth.grantsetter
    def set_grant(client_id, code, request, *args, **kwargs):
        return None

    @oauth.tokengetter
    def get_token(access_token=None, refresh_token=None):
        token_service = flask_injector.injector.get(TokenService)
        token = token_service.find(access_token,refresh_token)
        return token

    @oauth.tokensetter
    def set_token(token, request, *args, **kwargs):
        token_service = flask_injector.injector.get(TokenService)
        token = token_service.save(token, request)
        return token

    @oauth.usergetter
    def get_user(username, password, *args, **kwargs):
        user_service = flask_injector.injector.get(UserService)
        user = user_service.find_with_password(username,password)
        return user

    return oauth