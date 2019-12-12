import datetime

from flask_injector import inject
from flask_sqlalchemy import SQLAlchemy

from nisse.models.database import User, FoodOrder, FoodOrderItem


class FoodOrderService(object):
    """ FoodOrder service
    """
    @inject
    def __init__(self, db: SQLAlchemy):
        self.db = db

    def create_food_order(self, ordering_person: User, order_date: datetime, link: str):
        food_order = FoodOrder(ordering_user_id=ordering_person.user_id,
                               order_date=order_date,
                               link=link)
        self.db.session.add(food_order)
        self.db.session.commit()
        return food_order

    def create_food_order_item(self, order: FoodOrder, eating_person: User, desc: str,
                               cost: float=None):

        food_order_item = FoodOrderItem(food_order_id=order.food_order_id,
                                        eating_user_id=eating_person.user_id,
                                        description=desc,
                                        cost=cost)

        self.db.session.add(food_order_item)
        self.db.session.commit()
        return food_order_item
