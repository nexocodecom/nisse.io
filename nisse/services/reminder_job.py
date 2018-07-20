from datetime import datetime, timedelta

from flask_bcrypt import Bcrypt
from slackclient import SlackClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nisse.services import UserService
from nisse.services.slack.slack_command_service import CALLBACK_TOKEN_REMINDER_REPORT_BTN


def get_users_to_notify(logger, config):
    engine = create_engine(config['SQLALCHEMY_DATABASE_URI'], connect_args={
        'port': config['SQLALCHEMY_DATABASE_PORT']
    })
    session_maker = sessionmaker(bind=engine)
    try:
        session = session_maker()
        user_service = UserService(session, Bcrypt())
        return user_service.get_users_to_notify(datetime.utcnow().date(), datetime.utcnow().weekday(),
                                                (datetime.utcnow() - timedelta(minutes=5)).time(),
                                                datetime.utcnow().time())
    except Exception as e:
        logger.error(e)
        raise
    finally:
        session.close()


def remind(logger, config):
    logger.info('Reminder job started: ' + str(datetime.utcnow().time()))
    slack_client = SlackClient(config['SLACK_BOT_ACCESS_TOKEN'])

    users = get_users_to_notify(logger, config)

    for user in users:
        logger.info('Sending notification for user: ' + user.username)
        user_details = slack_client.api_call(
            "users.lookupByEmail",
            email=user.username
        )

        if not user_details["ok"]:
            logger.error("Can't get user details for user id: " + str(user.user_id) + '. ' + user_details["error"])

        im_channel = slack_client.api_call(
            "im.open",
            user=user_details['user']['id'])

        if not im_channel["ok"]:
            logger.error("Can't open im channel for: " + str(user.user_id) + '. ' + im_channel["error"])

        resp = slack_client.api_call(
            "chat.postMessage",
            channel=im_channel['channel']['id'],
            text="It looks like you didn't report work time for `Today`",
            mrkdwn=True,
            attachments=[
                {
                    "text": "Click 'Report' or use */tt* command:",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "callback_id": CALLBACK_TOKEN_REMINDER_REPORT_BTN,
                    "actions": [
                        {
                            "name": "report",
                            "text": "Report",
                            "style": "success",
                            "type": "button"
                        }
                    ],
                    "mrkdwn_in": ["text"]
                },
                {
                    "text": "",
                    "footer": "Use */ni reminder* to check yours reminder settings",
                    "mrkdwn_in": ["footer"]
                }
            ],
            as_user=True
        )

        if not resp["ok"]:
            logger.error("Can't send reminder message to user id: " + str(user.user_id) + '. ' + user_details["error"])

    logger.info('Reminder job finished: ' + str(datetime.utcnow().time()))
