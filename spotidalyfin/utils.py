# utils.py
import re
import sys

from loguru import logger

from spotidalyfin.constants import DEBUG


def slugify(value):
    return re.sub(r'[^\w_. -]', '_', value)


def format_string(string, removes=None):
    if removes is None:
        removes = [" '", "' ", "(", ")", "[", "]", "- ", " -", "And "]
    string = string.lower()
    for remove in removes:
        string = string.replace(remove, "")
    return string


def format_path(*parts):
    return "/".join(str(part).replace(" ", "_").lower() for part in parts)


def setup_logger():
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="DEBUG" if DEBUG else "INFO"
    )


def log_not_found_tracks(not_found):
    if not_found:
        logger.warning("Songs that could not be matched:")
        for track in not_found:
            track_name = track.get('name', '')
            artist_name = track.get('artists', [{}])[0].get('name', '')
            album_name = track.get('album', {}).get('name', '')
            logger.warning(f"{track_name} - {artist_name} ({album_name})")
        print()
