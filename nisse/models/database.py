from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DECIMAL, ForeignKey,DATETIME, Date, Time
from sqlalchemy.orm import relationship

Base = declarative_base()


class TimeEntry(Base):
    __tablename__ = "time_entries"

    time_entry_id = Column(Integer, primary_key=True)
    duration = Column(DECIMAL(precision=18, scale=2))
    comment = Column(String(length=255))
    user_id = Column(Integer, ForeignKey('users.user_id'))
    project_id = Column(Integer, ForeignKey('projects.project_id'))
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
    username = Column(String(length=100), unique=True)
    slack_user_id = Column(String(length=100), unique=True)
    first_name = Column(String(length=100))
    last_name = Column(String(length=100))
    password = Column(String(length=80))
    role_id = Column(Integer, ForeignKey('user_roles.user_role_id'))
    role = relationship("UserRole", back_populates="users_in_role")
    user_projects = relationship("UserProject", back_populates="user")
    user_time_entries = relationship('TimeEntry', back_populates='user')
    user_days_off = relationship('Dayoff', back_populates='user')
    remind_time_monday = Column(Time, nullable=True)
    remind_time_tuesday = Column(Time, nullable=True)
    remind_time_wednesday = Column(Time, nullable=True)
    remind_time_thursday = Column(Time, nullable=True)
    remind_time_friday = Column(Time, nullable=True)
    remind_time_saturday = Column(Time, nullable=True)
    remind_time_sunday = Column(Time, nullable=True)

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


class Client(Base):
    """ Client application through which user is authenticating.

        RFC 6749 Section 2 (http://tools.ietf.org/html/rfc6749#section-2)
        describes clients:

        +----------+
         | Resource |
         |  Owner   |
         |          |
         +----------+
              v
              |    Resource Owner
             (A) Password Credentials
              |
              v
         +---------+                                  +---------------+
         |         |>--(B)---- Resource Owner ------->|               |
         |         |         Password Credentials     | Authorization |
         | Client  |                                  |     Server    |
         |         |<--(C)---- Access Token ---------<|               |
         |         |    (w/ Optional Refresh Token)   |               |
         +---------+                                  +---------------+

        Redirection URIs are mandatory for clients. We skip this requirement
        as this example only allows the resource owner password credentials
        grant (described in Section 4.3). In this flow, the Authorization
        Server will not redirect the user as described in subsection 3.1.2
        (Redirection Endpoint).

        """
    __tablename__ = "clients"
    client_id = Column(String(length=40), primary_key=True)
    client_type = Column(String(length=40))

    @property
    def allowed_grant_types(self):
        """ Returns allowed grant types.

        Presently, only the password grant type is allowed.
        """
        return ['password']

    @property
    def default_scopes(self):
        """ Returns default scopes associated with the Client. """
        return []

    def default_redirect_uri():
        """ Return a blank default redirect URI since we are not implementing
            redirects.
        """
        return '' 

    
class Token(Base):
    """ Access or refresh token

            Because of our current grant flow, we are able to associate tokens
            with the users who are requesting them. This can be used to track usage
            and potential abuse. Only bearer tokens currently supported.

        """
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True)
    client_id = Column(String(40), ForeignKey('clients.client_id'), nullable=False)
    client = relationship('Client')
    user_id = Column(Integer, ForeignKey('users.user_id'))
    user = relationship('User')
    token_type = Column(String(40))
    access_token = Column(String(255), unique=True)
    refresh_token = Column(String(255), unique=True)
    expires = Column(DATETIME)
    scopes = ['']


class Dayoff(Base):
    __tablename__ = "holidays"
    dayoff_id = Column(Integer, primary_key=True)
    start_date = Column(DATETIME, nullable=False)
    end_date = Column(DATETIME, nullable=False)
    reason = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    user = relationship('User', back_populates='user_days_off')

    


