import re
from datetime import datetime


def parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, '%d/%m/%Y').date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.strptime(date_str, '%d/%m/%y').date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.strptime(date_str, '%m/%Y').date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.strptime(date_str, '%Y').date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.strptime(date_str, '%%m/y').date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.strptime(date_str, '%y').date()
    except (TypeError, ValueError):
        pass


def separate_capitalize(period_str: str):
    match = re.search(r'\d', period_str)
    if not match:
        return ''
    return ' '.join((period_str[:match.start()].title(), period_str[match.start():]))