from flask_bcrypt import Bcrypt
from slackclient import SlackClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nisse.models.slack.payload import RemindTimeReportBtnPayload
from nisse.services import UserService
from nisse.services import VacationService
from nisse.utils.date_helper import *
from nisse.utils.string_helper import get_full_class_name


def get_users_to_notify(logger, config, date_from: date, date_to: date):
    engine = create_engine(config['SQLALCHEMY_DATABASE_URI'])
    session_maker = sessionmaker(bind=engine)
    session = None
    try:
        session = session_maker()
        user_service = UserService(session, Bcrypt())
        vacation_service = VacationService(session)

        result = []
        users = user_service.get_users_to_notify_last_period(minutes=5)
        for user in users:
            time_entries = user_service.get_time_entry_date_range(user.user_id, date_from, date_to)
            reported_days = set(map(lambda te: te.report_date, time_entries))
            vacations = vacation_service.get_vacations_by_dates(user.user_id, date_from, date_to)

            all_days = set(filter(lambda day: not is_holiday_poland(day) and not is_weekend(day),
                                  date_range(date_from, date_to + timedelta(days=1))))

            for vac in vacations:
                all_days -= set(date_range(vac.start_date, vac.end_date + timedelta(days=1)))

            dates_to_remind = sorted(all_days - reported_days)

            if len(dates_to_remind) > 0:
                result.append([user, dates_to_remind])

        return result

    except Exception as e:
        logger.error(e)
        raise
    finally:
        if session:
            session.close()


def get_everyday_slack_message(config, remind_date):

    return "It looks like you didn't report work time for `{0}`".format(remind_date.strftime("%A, %d %B")), [
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
                        "type": "button",
                        'value': remind_date.strftime("%Y-%m-%d"),
                    }
                ],
                "mrkdwn_in": ["text"]
            },
            {
                "text": "",
                "footer": config['MESSAGE_REMINDER_RUN_TIP'],
                "mrkdwn_in": ["footer"]
            },
        ]


def get_friday_slack_message(config, remind_dates):

    actions = []
    for (date) in remind_dates:
        actions.append(
            {
                "name": "report",
                "text": date.strftime("%A, %d %B"),
                "style": "success",
                "type": "button",
                "value": date.strftime("%Y-%m-%d"),
            })

    return "It looks like you didn't report work time for `This week`", [
            {
                "text": "Click appropriate buttons or use */ni* command:",
                "color": "#3AA3E3",
                "attachment_type": "default",
                "callback_id": get_full_class_name(RemindTimeReportBtnPayload),
                "actions": actions,
                "mrkdwn_in": ["text"]
            },
            {
                "text": "",
                "footer": config['MESSAGE_REMINDER_RUN_TIP'],
                "mrkdwn_in": ["footer"]
            },
        ]


def remind(logger, config):
    logger.info('Reminder job started: ' + str(datetime.utcnow().time()))

    remind_date = datetime.utcnow().date()
    if is_holiday_poland(remind_date):
        return

    slack_client = SlackClient(config['SLACK_BOT_ACCESS_TOKEN'])
    is_friday = date.today().weekday() == 4

    remind_from = remind_date - timedelta(days=6) if is_friday else remind_date

    users = get_users_to_notify(logger, config, remind_from, remind_date)

    for (user, dates) in users:
        logger.info('Sending notification for user: ' + user.username)

        im_channel = slack_client.api_call(
            "im.open",
            user=user.slack_user_id)

        if not im_channel["ok"]:
            logger.error("Can't open im channel for: " +
                         str(user.user_id) + '. ' + im_channel["error"])

        if is_friday and len(dates) > 1:
            message = get_friday_slack_message(config, dates)
        else:
            message = get_everyday_slack_message(config, remind_date)

        resp = slack_client.api_call(
            "chat.postMessage",
            channel=im_channel['channel']['id'],
            text=message[0],
            attachments=message[1],
            mrkdwn=True,
            as_user=True
        )

        if not resp["ok"]:
            logger.error("Can't send reminder message to user id: " +
                         str(user.user_id) + '. ' + resp["error"])

    logger.info('Reminder job finished: ' + str(datetime.utcnow().time()))
