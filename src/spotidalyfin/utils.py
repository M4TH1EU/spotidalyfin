# utils.py
import re
import sys

from loguru import logger


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
        level="INFO"
    )
