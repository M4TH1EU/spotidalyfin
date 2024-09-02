# file_manager.py
import json
import shutil
from pathlib import Path

from loguru import logger
from minim.audio import Audio

from spotidalyfin import constants
from spotidalyfin.constants import FINAL_PATH, DOWNLOAD_PATH, DEBUG, APPLICATION_PATH


def format_file_path(metadata):
    def get_num(value, length=2):
        """Convert value to a zero-padded number string of specified length."""
        return str(value).zfill(length)

    # Extract necessary metadata
    album_artist = metadata.get('albumartist') or metadata.get('artist')
    artist = metadata.get('artist', '')
    album = metadata.get('album', '')
    total_discs = int(metadata.get('totaldiscs', 1))
    disc_number = int(metadata.get('discnumber', 1))
    track_number = metadata.get('tracknumber', 0)
    title = metadata.get('title', '')
    multiartist = metadata.get('_multiartist', False)

    # Build path components
    path = f"{album_artist}/"

    if album_artist and album:
        path += f"{album}/"

    if total_discs > 1:
        disc_part = f"{get_num(disc_number)}-" if total_discs > 9 else f"{disc_number}-"
        path += disc_part

    if album_artist and track_number:
        path += f"{get_num(track_number)} "

    if multiartist and artist:
        path += f"{artist} - "

    path += f"{title}"

    return path


def organize_downloaded_tracks():
    logger.info(f"Organizing tracks in {DOWNLOAD_PATH}")
    for track_path in DOWNLOAD_PATH.glob("*.flac"):
        if track_path.is_file():
            organize_track(track_path)
            logger.debug(f"Organized: {track_path.name}")

    if not DEBUG:
        for track_path in DOWNLOAD_PATH.glob("*.txt"):
            if track_path.is_file():
                track_path.unlink()

        # Remove artwork folder if it exists
        (DOWNLOAD_PATH / "__artwork").unlink(missing_ok=True)

    logger.success("Organized downloaded tracks.\n")


def organize_track(file_path: Path):
    audio_data = Audio(file_path)
    metadata = {
        "albumartist": audio_data.album_artist,
        "artist": audio_data.artist,
        "album": audio_data.album,
        "title": audio_data.title,
        "totaldiscs": audio_data.disc_count,
        "discnumber": audio_data.disc_number,
        "tracknumber": audio_data.track_number,
        "_multiartist": False,
    }

    formatted_path = format_file_path(metadata) + file_path.suffix  # Author/Album/00 Track title
    new_path = Path(FINAL_PATH) / formatted_path
    new_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.move(file_path, new_path)


def check_downloaded_tracks(tidal_urls):
    amount = len(tidal_urls)
    downloaded = len(list(DOWNLOAD_PATH.glob("*.flac")))

    if amount == downloaded:
        logger.success(f"All {amount} tracks downloaded successfully!\n")
    else:
        logger.warning(f"Only {downloaded} out of {amount} tracks downloaded successfully.\n")


def apply_json_config(data: dict, file_path: Path):
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)
        logger.debug(f"Config written to {file_path}")


def check_bundled_secrets():
    secrets = APPLICATION_PATH / "spotidalyfin.secrets"
    if secrets.exists():
        load_secrets(secrets)


def load_secrets(file_path: Path):
    secrets = {}
    with open(file_path, 'r') as f:
        for line in f:
            key, value = line.strip().split("=", 1)  # Strip spaces and split on the first '='
            secrets[key.strip()] = value.strip()

    if 'SPOTIFY_CLIENT_ID' in secrets:
        constants.SPOTIFY_CLIENT_ID = secrets['SPOTIFY_CLIENT_ID']
    if 'SPOTIFY_CLIENT_SECRET' in secrets:
        constants.SPOTIFY_CLIENT_SECRET = secrets['SPOTIFY_CLIENT_SECRET']
    if 'TIDAL_CLIENT_ID' in secrets:
        constants.TIDAL_CLIENT_ID = secrets['TIDAL_CLIENT_ID']
    if 'TIDAL_CLIENT_SECRET' in secrets:
        constants.TIDAL_CLIENT_SECRET = secrets['TIDAL_CLIENT_SECRET']
    if 'JELLYFIN_URL' in secrets:
        constants.JELLYFIN_URL = secrets['JELLYFIN_URL']
    if 'JELLYFIN_API_KEY' in secrets:
        constants.JELLYFIN_API_KEY = secrets
