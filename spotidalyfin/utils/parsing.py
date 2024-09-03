from datetime import datetime


def parse_date(date_str: str):
    """Parse a date string into a datetime object."""
    formats = {
        4: '%Y',
        7: '%Y-%m',
        10: '%Y-%m-%d'
    }
    date_format = formats.get(len(date_str))
    return datetime.strptime(date_str, date_format) if date_format else None
