from datetime import datetime, timedelta

from flask_bcrypt import Bcrypt
from slackclient import SlackClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nisse.models.slack.payload import RemindTimeReportBtnPayload
from nisse.services import UserService
from nisse.utils.string_helper import get_full_class_name


def get_users_to_notify(logger, config):
    engine = create_engine(config['SQLALCHEMY_DATABASE_URI'])
    session_maker = sessionmaker(bind=engine)
    session = None
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
        if session:
            session.close()


def remind(logger, config):
    logger.info('Reminder job started: ' + str(datetime.utcnow().time()))
    slack_client = SlackClient(config['SLACK_BOT_ACCESS_TOKEN'])

    users = get_users_to_notify(logger, config)

    for user in users:
        logger.info('Sending notification for user: ' + user.username)

        im_channel = slack_client.api_call(
            "im.open",
            user=user.slack_user_id)

        if not im_channel["ok"]:
            logger.error("Can't open im channel for: " + str(user.user_id) + '. ' + im_channel["error"])

        resp = slack_client.api_call(
            "chat.postMessage",
            channel=im_channel['channel']['id'],
            text="It looks like you didn't report work time for `Today`",
            mrkdwn=True,
            attachments=[
                {
                    "text": "Click 'Report' or use */ni* command:",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "callback_id": get_full_class_name(RemindTimeReportBtnPayload),
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
                    "footer": config['MESSAGE_REMINDER_RUN_TIP'],
                    "mrkdwn_in": ["footer"]
                }
            ],
            as_user=True
        )

        if not resp["ok"]:
            logger.error("Can't send reminder message to user id: " + str(user.user_id) + '. ' + resp["error"])

    logger.info('Reminder job finished: ' + str(datetime.utcnow().time()))
