import logging
import shutil
from pathlib import Path

from minim.audio import Audio

from spotidalyfin.utils.logger import log


def file_to_list(file_path: Path) -> list:
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines() if line.strip()]


def get_all_files_in_directory(directory: Path) -> list:
    """Get all files in a directory."""
    return [file for file in directory.rglob("*") if file.is_file()]


def parse_secrets_file(secrets_file: Path) -> dict:
    """Parse a secrets file into a dictionary."""
    secrets = {}

    if secrets_file.exists():
        with open(secrets_file, 'r') as file:
            for line in file.readlines():
                line = line.replace(" ", "").strip().split('=', maxsplit=1)
                if len(line) == 2:
                    key, value = line
                    secrets[key.lower()] = value

    return secrets


def format_track_path_from_file_metadata(file: Path) -> str:
    audio_data = Audio(file)
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

    def get_num(value, length=2):
        """Convert value to a zero-padded number string of specified length."""
        return str(value).zfill(length)

    if None in metadata.values():
        log.error(f"Missing metadata for {file}. File is probably corrupted.")
        return ""

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
    path += file.suffix

    return path


def organize_audio_files(files_path: Path, output_path: Path):
    """Organize audio files based on their metadata."""
    for file in files_path.rglob("*"):
        organize_audio_file(file, output_path)


def organize_audio_file(file_path: Path, output_path: Path):
    """Organize a single audio file based on its metadata."""
    if file_path.is_file() and file_path.suffix.lower() in [".mp3", ".flac", ".m4a"]:
        path = format_track_path_from_file_metadata(file_path)
        if path:
            destination = output_path / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(file_path, destination)
            logging.debug(f"Moved {file_path} to {destination}")
