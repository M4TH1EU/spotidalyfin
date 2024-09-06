from pathlib import Path

from spotidalyfin import APPLICATION_PATH

_config = {
    "debug": False,
    "out-dir": Path("~/Music/spotidalyfin").expanduser(),
    "dl-dir": Path("/tmp/spotidalyfin"),
    "config-dir": Path("~/.config/spotidalyfin").expanduser(),
    "secrets": APPLICATION_PATH / "spotidalyfin.secrets",
    "quality": 3,
    "jellyfin-metadata-dir": Path("/var/lib/jellyfin/metadata")
}


def get(key, default=None):
    return _config.get(key, default)


def put(key, value):
    _config[key] = value


def get_config():
    return _config
