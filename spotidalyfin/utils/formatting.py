import datetime

from tidalapi import Artist


def format_path(*parts):
    return "/".join(str(part).replace(" ", "_").lower() for part in parts)


def format_string(string: str) -> str:
    """Format a string by removing content after certain delimiters and stripping whitespace."""
    return string.split('-')[0].strip().split('(')[0].strip().split('[')[0].strip()


def format_artists(artists: list, lower: bool = True) -> list:
    """Format a tidal/spotify list of artist names by handling multiple separators and converting to lowercase."""
    formatted_artists = []
    for artist in artists:
        artist_name = ""

        if isinstance(artist, dict):
            artist_name = artist.get('name', '')
        elif isinstance(artist, Artist):
            artist_name = artist.name

        for sep in ['&', 'and', ',']:
            if sep in artist_name:
                artist_name = artist_name.split(sep)
                break

        if isinstance(artist_name, list):
            formatted_artists.extend(a.strip().lower() if lower else a.strip() for a in artist_name)
        else:
            formatted_artists.append(artist_name.strip().lower() if lower else artist_name.strip())

    return formatted_artists


def parse_date(date_str: str):
    """Parse a date string into a datetime object."""
    formats = {
        4: '%Y',
        7: '%Y-%m',
        10: '%Y-%m-%d',
        16: '%Y-%m-%d %H:%M',
        19: '%Y-%m-%d %H:%M:%S'
    }
    date_format = formats.get(len(date_str))
    return datetime.strptime(date_str, date_format) if date_format else None


def not_none(any) -> str:
    return str(any) if any else ""


def num(any):
    try:
        return int(any)
    except ValueError:
        return 0
