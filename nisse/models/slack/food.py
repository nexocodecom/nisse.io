from sqlalchemy import Integer

class UserDebt(object):

    def __init__(self, user_id: Integer, debt: float):
        self.user_id = user_id
        self.debt = debt
