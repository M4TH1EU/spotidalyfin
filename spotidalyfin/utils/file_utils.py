import subprocess
import tempfile
from pathlib import Path

import requests
from ffmpeg import FFmpeg, FFmpegError

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


def open_image_url(url: str) -> bytes:
    """Open an image URL and return the image data."""
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile() as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
        f.seek(0)
        return f.read()


def extract_flac_from_mp4(file_path: Path, timeout=15) -> Path:
    """Extract a FLAC audio file from an MP4 file."""
    file_out = file_path.with_suffix(".flac")

    try:
        FFmpeg().option("y").input(str(file_path)).output(str(file_out), {"f": "flac"}).execute(timeout=timeout)
    except FFmpegError as e:
        log.error(f"Error extracting FLAC from MP4: {e}")
        return file_path
    except subprocess.TimeoutExpired:
        log.error(f"Timeout extracting FLAC from MP4")
        return file_path

    file_path.unlink()
    return file_out


def get_size_of_folder(folder: Path) -> int:
    """Get the size of a folder in bytes."""
    return sum(file.stat().st_size for file in get_all_files_in_directory(folder))
