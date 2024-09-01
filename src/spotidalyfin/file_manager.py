# file_manager.py
import shutil
from pathlib import Path

from minim.audio import Audio

from src.spotidalyfin.constants import FINAL_PATH


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
