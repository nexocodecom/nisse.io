from flask_sqlalchemy import SQLAlchemy
from flask_injector import inject
from sqlalchemy import or_
from nisse.models.database import Vacation
import datetime


class VacationService(object):
    """ Vacation service
    """
    @inject
    def __init__(self, db: SQLAlchemy):
        self.db = db

    def get_user_days_off(self, user_id):
        return self.db.session.query(Vacation) \
            .filter(Vacation.user_id == user_id) \
            .all()

    def get_user_vacations_since(self, user_id, since_date):
        return self.db.session.query(Vacation) \
            .filter(or_(Vacation.start_date > since_date, since_date < Vacation.end_date)) \
            .all()

    def insert_user_vacation(self, user_id, start_date, end_date, reason):
        vacation = Vacation(user_id=user_id, start_date=start_date,
                         end_date=end_date, reason=reason)
        self.db.session.add(vacation)
        self.db.session.commit()
        return vacation
