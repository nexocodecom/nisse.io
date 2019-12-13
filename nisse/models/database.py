from sqlalchemy import Column, Integer, String, DECIMAL, ForeignKey, Date, Time, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class TimeEntry(Base):
    __tablename__ = "time_entries"

    time_entry_id = Column(Integer, primary_key=True)
    duration = Column(DECIMAL(precision=18, scale=2))
    comment = Column(String(length=255))
    user_id = Column(Integer, ForeignKey('users.user_id'), index=True)
    project_id = Column(Integer, ForeignKey('projects.project_id'), index=True)
    user = relationship('User', back_populates='user_time_entries', lazy='joined')
    project = relationship('Project', back_populates='project_time_entries')
    report_date = Column(Date)


class Project(Base):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True)
    name = Column(String(length=100))
    project_users = relationship('UserProject', back_populates='project')
    project_time_entries = relationship('TimeEntry', back_populates='project')


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    username = Column(String(length=100), unique=True, index=True)
    slack_user_id = Column(String(length=100), unique=True)
    first_name = Column(String(length=100))
    last_name = Column(String(length=100))
    password = Column(String(length=80))
    role_id = Column(Integer, ForeignKey('user_roles.user_role_id'), index=True)
    role = relationship("UserRole", back_populates="users_in_role")
    user_projects = relationship("UserProject", back_populates="user")
    user_time_entries = relationship('TimeEntry', back_populates='user')
    vacations = relationship('Vacation', back_populates='user')
    remind_time_monday = Column(Time, nullable=True)
    remind_time_tuesday = Column(Time, nullable=True)
    remind_time_wednesday = Column(Time, nullable=True)
    remind_time_thursday = Column(Time, nullable=True)
    remind_time_friday = Column(Time, nullable=True)
    remind_time_saturday = Column(Time, nullable=True)
    remind_time_sunday = Column(Time, nullable=True)
    phone = Column(String(length=15))

class UserRole(Base):
    __tablename__ = "user_roles"

    user_role_id = Column(Integer, primary_key=True)
    role = Column(String(length=100))
    users_in_role = relationship(
        "User", order_by=User.user_id, back_populates='role')


class UserProject(Base):
    __tablename__ = "user_projects"

    user_project_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    project_id = Column(Integer, ForeignKey('projects.project_id'))
    user = relationship('User', back_populates='user_projects')
    project = relationship('Project', back_populates='project_users')

    
class Token(Base):
    """ Access or refresh token

            Because of our current grant flow, we are able to associate tokens
            with the users who are requesting them. This can be used to track usage
            and potential abuse. Only bearer tokens currently supported.

        """
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True)
    token = Column(String(255), unique=True)
    refresh_token = Column(String(255), unique=True, index=True)
    token_uri = Column(String(255))
    client_id = Column(String(255), nullable=False, unique=True, index=True)
    client_secret = Column(String(255))
    scopes = Column(String(4096))


class Vacation(Base):
    __tablename__ = "vacations"
    vacation_id = Column(Integer, primary_key=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    event_id = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    user = relationship('User', back_populates='vacations')


class FoodOrder(Base):
    __tablename__ = "food_order"

    food_order_id = Column(Integer, primary_key=True)
    order_date = Column(Date, nullable=False)
    ordering_user_id = Column(Integer, ForeignKey('users.user_id'))
    link = Column(String(length=512))
    reminder = Column(String(length=32))


class FoodOrderItem(Base):
    __tablename__ = "food_order_item"

    food_order_item_id = Column(Integer, primary_key=True)
    food_order_id = Column(Integer, ForeignKey('food_order.food_order_id'))
    eating_user_id = Column(Integer, ForeignKey('users.user_id'))
    description = Column(String(length=255))
    cost = Column(DECIMAL(precision=18, scale=2), nullable=False)
    paid = Column(Boolean, nullable=False)
    surrender = Column(Boolean, nullable=False)



