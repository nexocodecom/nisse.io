from flask_sqlalchemy import SQLAlchemy
from flask_injector import inject
from sqlalchemy import or_
from nisse.models.database import Dayoff
import datetime


class DayOffService(object):
    """ Project service
    """
    @inject
    def __init__(self, db: SQLAlchemy):
        self.db = db

    def get_user_days_off(self, user_id):
        return self.db.session.query(Dayoff) \
            .filter(Dayoff.user_id == user_id) \
            .all()

    def get_user_days_off_since(self, user_id, since_date):
        return self.db.session.query(Dayoff) \
            .filter(or_(Dayoff.start_date > since_date, since_date < Dayoff.end_date)) \
            .all()

    def insert_user_day_off(self, user_id, start_date, end_date, reason):
        day_off = Dayoff(user_id=user_id, start_date=start_date,
                         end_date=end_date, reason=reason)
        self.db.session.add(day_off)
        self.db.session.commit()
        return day_off
