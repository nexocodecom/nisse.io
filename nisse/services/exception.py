from dataclasses import dataclass


@dataclass
class DataException(Exception):
    field: str
    message: str
