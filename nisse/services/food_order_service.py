from datetime import date

from flask_injector import inject
from flask_sqlalchemy import SQLAlchemy

from nisse.models.database import User, FoodOrder, FoodOrderItem


class FoodOrderService(object):
    """ FoodOrder service
    """
    @inject
    def __init__(self, db: SQLAlchemy):
        self.db = db

    def create_food_order(self, ordering_person: User, order_date: date, link: str, reminder: str) -> FoodOrder:
        food_order = FoodOrder(ordering_user_id=ordering_person.user_id,
                               order_date=order_date,
                               link=link,
                               reminder=reminder)
        self.db.session.add(food_order)
        self.db.session.commit()
        return food_order

    def create_food_order_item(self, order: FoodOrder, eating_person: User, desc: str,
                               cost: float=None) -> FoodOrderItem:

        food_order_item = FoodOrderItem(food_order_id=order.food_order_id,
                                        eating_user_id=eating_person.user_id,
                                        description=desc,
                                        cost=cost)

        self.db.session.add(food_order_item)
        self.db.session.commit()
        return food_order_item

    def checkout_order(self, ordering_person: User, order_date: date):
        date_str = order_date.isoformat()
        original = self.db.session.query(FoodOrder) \
            .filter(FoodOrder.order_date == date_str and FoodOrder.ordering_user_id == ordering_person.user_id). \
            first()
        if not original:
            return None

        reminder = original.reminder
        self.db.session.query(FoodOrder) \
            .filter(FoodOrder.order_date == date_str and FoodOrder.ordering_user_id == ordering_person.user_id). \
            update({FoodOrder.reminder: ""})
        self.db.session.commit()
        return reminder
