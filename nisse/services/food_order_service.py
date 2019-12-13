from datetime import date
from pprint import pprint

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

        self.remove_food_order(order_date)

        self.db.session.add(food_order)
        self.db.session.commit()
        return food_order

    def create_food_order_item(self, order: FoodOrder, eating_person: User, desc: str,
                               cost: float=None) -> FoodOrderItem:
        self.remove_food_order_item(order.food_order_id, eating_person)
        food_order_item = FoodOrderItem(food_order_id=order.food_order_id,
                                        eating_user_id=eating_person.user_id,
                                        description=desc,
                                        surrender=False,
                                        cost=cost)
        self.db.session.add(food_order_item)
        self.db.session.commit()
        return food_order_item

    def skip_food_order_item(self, order_id: str, eating_person: User):
        self.remove_food_order_item(order_id, eating_person)

        food_order_item = FoodOrderItem(food_order_id=order_id,
                                        eating_user_id=eating_person.user_id,
                                        description='',
                                        surrender=True,
                                        cost=0.0)
        self.db.session.add(food_order_item)
        self.db.session.commit()
        return food_order_item

    def get_food_order_items_by_date(self, ordering_person: User, order_date: date):
        order = self.get_order_by_date(ordering_person, order_date)
        if not order:
            return None

        return self.db.session.query(FoodOrderItem) \
            .filter(FoodOrderItem.food_order_id == order.food_order_id)


    def remove_food_order(self, order_date: date):
        date_str = order_date.isoformat()
        removed_orders: [FoodOrder]= self.db.session.query(FoodOrder) \
            .filter(FoodOrder.order_date == date_str)

        if removed_orders:
            for removed_order in removed_orders:
                self.remove_food_order_item_for_order(removed_order)
                self.db.session.commit()
                self.db.session.delete(removed_order)
                self.db.session.commit()

    def remove_food_order_item(self, food_order_id: str, eating_person: User):
        overriden_order_item: FoodOrderItem = self.db.session.query(FoodOrderItem) \
            .filter(FoodOrderItem.eating_user_id == eating_person.user_id) \
            .filter(FoodOrderItem.food_order_id == food_order_id) \
            .first()
        if overriden_order_item is not None:
            self.db.session.delete(overriden_order_item)
            self.db.session.commit()

    def remove_food_order_item_for_order(self, removed_order: FoodOrder):
        removed_order_items: [FoodOrderItem] = self.db.session.query(FoodOrderItem) \
            .filter(FoodOrderItem.food_order_id == removed_order.food_order_id)
        print("Removing orders: ", removed_order_items)
        if removed_order_items:
            for removed_order_item in removed_order_items:
                self.db.session.delete(removed_order_item)


    def checkout_order(self, ordering_person: User, order_date: date):
        original = self.get_order_by_date(ordering_person, order_date)
        if not original:
            return None

        date_str = order_date.isoformat()
        reminder = original.reminder
        self.db.session.query(FoodOrder) \
            .filter(FoodOrder.order_date == date_str and FoodOrder.ordering_user_id == ordering_person.user_id). \
            update({FoodOrder.reminder: ""})
        self.db.session.commit()
        return reminder

    def get_order_by_date(self, ordering_person: User, order_date: date):
        date_str = order_date.isoformat()
        return self.db.session.query(FoodOrder) \
            .filter(FoodOrder.order_date == date_str and FoodOrder.ordering_user_id == ordering_person.user_id). \
            first()
