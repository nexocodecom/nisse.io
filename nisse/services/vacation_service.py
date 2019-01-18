from flask_injector import inject
from sqlalchemy import or_
from sqlalchemy.orm import Session

from nisse.models.database import Vacation


class VacationService(object):
    """ Vacation service
    """
    @inject
    def __init__(self, session: Session):
        self.db = session

    def get_user_days_off(self, user_id):
        return self.db.query(Vacation) \
            .filter(Vacation.user_id == user_id) \
            .all()

    def get_user_vacations_since(self, user_id, since_date):
        return self.db.query(Vacation) \
            .filter(Vacation.user_id == user_id) \
            .filter(or_(Vacation.start_date > since_date, since_date < Vacation.end_date)) \
            .all()

    def get_ten_newest_user_vacations(self, user_id):
        return self.db.query(Vacation) \
            .filter(Vacation.user_id == user_id) \
            .order_by(Vacation.start_date.desc()) \
            .limit(10) \
            .all()

    def get_vacations_by_dates(self, user_id, date_from, date_to):
        return self.db.query(Vacation) \
            .filter(Vacation.user_id == user_id) \
            .filter(or_(Vacation.start_date.between(date_from, date_to),
                        Vacation.end_date.between(date_from, date_to))) \
            .all()

    def get_vacation_by_id(self, user_id: int, vacation_id: int) -> Vacation:
        return self.db.query(Vacation)\
            .filter(vacation_id == Vacation.vacation_id) \
            .filter(user_id == Vacation.user_id) \
            .first()

    def delete_vacation(self, user_id: int, vacation_id: int):
        vacation = self.get_vacation_by_id(user_id=user_id, vacation_id=vacation_id)
        self.db.delete(vacation)
        self.db.commit()

    def insert_user_vacation(self, user_id, start_date, end_date, event_id):
        vacation = Vacation(user_id=user_id, start_date=start_date, end_date=end_date, event_id=event_id)
        self.db.add(vacation)
        self.db.commit()
        return vacation
