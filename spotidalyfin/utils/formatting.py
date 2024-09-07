import datetime
import re

from tidalapi import Artist


def format_path(*parts):
    return "/".join(str(part).replace(" ", "_").lower() for part in parts)


def format_string(string: str) -> str:
    """Format a string by removing content after certain delimiters and stripping whitespace."""
    return string.strip().split('(')[0].strip().split('[')[0].strip().lower()


def normalize_str(text: str, remove_in_brackets: bool = False, try_fix_track_name: bool = False,
                  stop_at_dash_char: bool = False) -> str:
    if stop_at_dash_char:
        text = text.split(" - ")[0]

    if try_fix_track_name:
        if len(text.split(" - ")) == 2:
            # Convert "Song - From ..." to "Song (From ...)" (example)
            text = text.replace(" - ", " (") + ")"

    if remove_in_brackets:
        # Removes everything in parentheses
        text = re.sub(r'\([^)]*\)', '', text)

    words_to_remove = ["Album", "Original", "Remastered", "Remaster", "Version", "Edit", "Explicit", "Deluxe", "Bonus"]
    for word in words_to_remove:
        text = text.replace(word, "")

    text = text.strip()
    return text


def normalize(text: str) -> list[str]:
    """Normalize text by tokenizing, converting to lowercase, and removing stopwords and non-alphanumeric characters."""
    text = text.lower()

    # Removes various stuff in parentheses (e.g. (feat. ...), (from ...), (edition ...), (radio ...), (bande ...), etc.)
    text = re.sub(r'\((feat|with|edition|radio|bande|original|ultimate)[^)]*\)', '', text)
    text = re.sub(r'\(uk.*?album\)', '', text)
    text = text.replace("remix", "")
    # Removes date and version information (e.g. 2020 remaster, 2020 version, etc.)
    # text = re.sub(r'\d{4} (remaster|version)', '', text)

    tokens = text.split()
    tokens = [re.sub(r'\W+', '', token) for token in tokens]  # Remove non-alphanumeric characters

    tokens = [token for token in tokens if token != '']
    return tokens


def format_artists(artists: list | str, lower: bool = True) -> list:
    """Format a tidal/spotify list of artist names by handling multiple separators and converting to lowercase."""
    formatted_artists = []
    if isinstance(artists, str):
        artists = [artists]

    for artist in artists:
        artist_name = ""

        if isinstance(artist, dict):
            artist_name = artist.get('name', '')
        elif isinstance(artist, Artist):
            artist_name = artist.name
        elif isinstance(artist, str):
            artist_name = artist

        # Fix for "Yusuf / Cat Stevens"
        if "/ " in artist_name:
            artist_name = artist_name.split("/ ")[1]

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


def not_none(any, default=None) -> str:
    try:
        return str(any) if any else "" if default is None else default
    except:
        return "" if default is None else default


def num(any):
    try:
        return int(any)
    except ValueError:
        return 0
