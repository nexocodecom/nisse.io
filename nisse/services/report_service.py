from flask_sqlalchemy import SQLAlchemy
from flask_injector import inject
from nisse.models.database import TimeEntry
from nisse.models.DTO import *


class ReportService(object):
    """
    Loads data to generate report
    """
    @inject
    def __init__(self, db: SQLAlchemy):
        self.db = db

    def load_report_data(self, print_parameters: PrintParameters):
        query = self.db.session.query(TimeEntry)
        query = self.apply_parameters(query, print_parameters)
        return query.all()

    @staticmethod
    def apply_parameters(query, print_parameters):
        for attr, value in print_parameters.__dict__.items():
            query = getattr(QueryBuilder, attr)(query, print_parameters)
        return query


class QueryBuilder(object):
    """
    Every PrintParameters attribute needs to be handled here
    otherwise AttributeError exception will be thrown
    """
    @staticmethod
    def user_id(query, parameters: PrintParameters):
        if parameters.user_id is None:
            return query
        return query.filter(parameters.user_id == TimeEntry.user_id)

    @staticmethod
    def project_id(query, parameters: PrintParameters):
        if parameters.project_id is None:
            return query
        return query.filter(parameters.project_id == TimeEntry.project_id)

    @staticmethod
    def date_from(query, parameters: PrintParameters):
        if parameters.date_from is None:
            return query
        return query.filter(parameters.date_from <= TimeEntry.report_date)

    @staticmethod
    def date_to(query, parameters: PrintParameters):
        if parameters.date_to is None:
            return query
        return query.filter(parameters.date_to >= TimeEntry.report_date)
