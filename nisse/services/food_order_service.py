from datetime import date
from pprint import pprint

from flask_injector import inject
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc
from typing import List

from nisse.models.database import User, FoodOrder, FoodOrderItem
from nisse.models.slack.food import UserDebt


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
        paid = order.ordering_user_id == eating_person.user_id
        self.remove_food_order_item(order.food_order_id, eating_person)
        food_order_item = FoodOrderItem(food_order_id=order.food_order_id,
                                        eating_user_id=eating_person.user_id,
                                        description=desc,
                                        surrender=False,
                                        cost=cost,
                                        paid=paid)
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
            .filter(FoodOrder.order_date == date_str and FoodOrder.ordering_user_id == ordering_person.user_id) \
            .order_by(FoodOrder.food_order_id.asc())[-1]

    def get_order_by_date_only(self, order_date: date):
        date_str = order_date.isoformat()
        return self.db.session.query(FoodOrder) \
            .filter(FoodOrder.order_date == date_str) \
            .order_by(FoodOrder.food_order_id.asc())[-1]

    def get_debt(self, person: User) -> List[UserDebt]:
        owing_to = self.db.session.query(FoodOrder.ordering_user_id, func.sum(FoodOrderItem.cost).label('debt')) \
            .filter(FoodOrderItem.eating_user_id == person.user_id) \
            .filter(FoodOrderItem.food_order_id == FoodOrder.food_order_id) \
            .filter(FoodOrderItem.paid == 'f') \
            .group_by(FoodOrder.ordering_user_id) \
            .all()
        owing_me = self.db.session.query(FoodOrderItem.eating_user_id, func.sum(FoodOrderItem.cost).label('debt')) \
            .filter(FoodOrder.ordering_user_id == person.user_id) \
            .filter(FoodOrderItem.food_order_id == FoodOrder.food_order_id) \
            .filter(FoodOrderItem.paid == 'f') \
            .group_by(FoodOrderItem.eating_user_id) \
            .all()
        debts = {}
        for debt in owing_me:
            debts[debt[0]] = debt[1]
        for debt in owing_to:
            debts.setdefault(debt[0], 0)
            debts[debt[0]] -= debt[1]
        result: List[UserDebt] = []
        for user_id in sorted(debts):
            result.append(UserDebt(user_id, debts[user_id]))
        return result

    def pay_debts(self, paying_user: User, paid_user: User):
        print("{} paying all debts to {}".format(paying_user, paid_user))
        result = self.db.session.execute(
            "UPDATE food_order_item i SET paid = 't' FROM food_order o "
            "WHERE i.food_order_id=o.food_order_id "
            "AND i.eating_user_id IN (:u1,:u2) AND o.ordering_user_id IN (:u1,:u2) "
            "AND i.paid = 'f'",
            {'u1': paying_user.user_id, 'u2': paid_user.user_id}
        )
        self.db.session.commit()
        print("Paid {} debts".format(result.rowcount))

    def top_debtors(self) -> List[UserDebt]:
        return self.db.session.query(FoodOrderItem.eating_user_id, func.sum(FoodOrderItem.cost).label('debt')) \
            .filter(FoodOrderItem.food_order_id == FoodOrder.food_order_id) \
            .filter(FoodOrderItem.paid == 'f') \
            .group_by(FoodOrderItem.eating_user_id) \
            .order_by(desc('debt')) \
            .limit(3) \
            .all()
