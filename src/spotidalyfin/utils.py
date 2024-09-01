# utils.py
import re


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
