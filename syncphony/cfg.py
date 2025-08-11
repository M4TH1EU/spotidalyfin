from pathlib import Path

from syncphony import APPLICATION_PATH

_config = {
    "debug": False,
    "out-dir": Path("~/Music/syncphony").expanduser(),
    "dl-dir": Path("/tmp/syncphony"),
    "config-dir": Path("~/.config/syncphony").expanduser(),
    "secrets": APPLICATION_PATH / "syncphony.secrets",
    "quality": 3,
    "jellyfin-metadata-dir": Path("/var/lib/jellyfin/metadata")
}


def get(key, default=None):
    return _config.get(key, default)


def put(key, value):
    _config[key] = value


def get_config():
    return _config
