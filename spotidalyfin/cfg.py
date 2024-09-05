from pathlib import Path

from spotidalyfin import APPLICATION_PATH

QUALITIES = {
    "DOLBY_ATMOS": 0,
    "LOW": 1,
    "LOSSLESS": 2,
    "HI_RES_LOSSLESS": 3
}

QUALITIES_REVERSE = {v: k for k, v in QUALITIES.items()}

_config = {
    "debug": False,
    "out-dir": Path("~/Music/spotidalyfin").expanduser(),
    "dl-dir": Path("/tmp/spotidalyfin"),
    "secrets": APPLICATION_PATH / "spotidalyfin.secrets",
    "streamrip": APPLICATION_PATH / "streamrip",
    "quality": 3,
}


def get(key, default=None):
    return _config.get(key, default)


def put(key, value):
    _config[key] = value


def get_config():
    return _config
