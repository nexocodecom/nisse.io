from decimal import Decimal

from sqlalchemy import Integer


class UserDebt(object):

    def __init__(self, user_id: Integer, debt: Decimal):
        self.user_id = user_id
        self.debt = debt

    def __repr__(self):
        return "UserDebt({}, {})".format(self.user_id, self.debt)
