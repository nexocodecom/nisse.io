import datetime
from decimal import Decimal


def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def validate_date(date_text):
    try:
        datetime.datetime.strptime(date_text, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_price(price_text):
    try:
        price = Decimal(price_text.replace(",","."))
        if(price <= Decimal(0)):
            return False
        return True
    except ValueError:
        return False

def list_find(f, seq):
    """Return first item in sequence where f(item) == True."""
    for item in seq:
        if f(item):
            return item
