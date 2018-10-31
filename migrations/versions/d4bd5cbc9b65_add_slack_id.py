"""add_slack_id

Revision ID: d4bd5cbc9b65
Revises: 382223577313
Create Date: 2018-10-30 13:18:03.245627

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import orm
from nisse.models.database import User
from slackclient import SlackClient
from flask import Flask
from nisse.utils.configs import load_config

# revision identifiers, used by Alembic.
revision = 'd4bd5cbc9b65'
down_revision = '382223577313'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('slack_user_id', sa.String(length=100), nullable=True))

    application = Flask(__name__, instance_relative_config=True)
    load_config(application)

    slack_client = SlackClient(application.config['SLACK_BOT_ACCESS_TOKEN'])

    slack_user_list = slack_client.api_call(
        "users.list"
    )

    ids = dict()
    for s in slack_user_list['members']:
        if 'profile' in s and 'email' in s['profile']:
            ids[s['profile']['email']] = s['id']

    bind = op.get_bind()
    session = orm.Session(bind=bind)

    for user in session.query(User):
        fname = str(user.first_name).split(" ")
        user.first_name = fname[0]
        if len(fname) > 1:
            user.last_name = fname[1]
        if user.username in ids:
            user.slack_user_id = ids[user.username]

    session.commit()


def downgrade():

    bind = op.get_bind()
    session = orm.Session(bind=bind)

    for user in session.query(User):
        user.first_name = str(user.first_name + " " + user.last_name)
        user.last_name = None

    session.commit()

    op.drop_column('users', 'slack_user_id')

