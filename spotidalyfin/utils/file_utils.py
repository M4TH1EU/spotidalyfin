import hashlib
import subprocess
import tempfile
from pathlib import Path

import requests
from PIL import Image
from PIL.Image import Resampling
from ffmpeg import FFmpeg, FFmpegError

from spotidalyfin.utils.logger import log


def file_to_list(file_path: Path) -> list:
    """Read a file and return its lines as a list."""
    if not file_path.exists():
        return []

    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines() if line.strip()]


def write_line_to_file(file_path: Path, line: str):
    """Write a line to a file. Creates the file if it does not exist."""
    create_file(file_path)
    with open(file_path, 'a') as file:
        file.write(line + "\n")


def remove_line_from_file(file_path: Path, line: str):
    """Remove a line from a file. Does nothing if the file does not exist."""
    if not file_path.exists():
        return

    with open(file_path, 'r') as file:
        lines = file.readlines()
    with open(file_path, 'w') as file:
        for l in lines:
            if l.strip() != line:
                file.write(l)


def replace_line_in_file(file_path: Path, old_line: str, new_line: str):
    """Replace a line in a file. Does nothing if the file does not exist."""

    if not file_path.exists():
        return

    with open(file_path, 'r') as file:
        lines = file.readlines()
    with open(file_path, 'w') as file:
        for l in lines:
            if l.strip() == old_line:
                file.write(new_line + "\n")
            else:
                file.write(l)


def write_list_to_file(file_path: Path, data: list):
    """Write a list to a file. Creates the file if it does not exist."""
    create_file(file_path)
    with open(file_path, 'w') as file:
        for line in data:
            file.write(line + "\n")


def create_file(file_path: Path):
    """Create a file if it does not exist."""
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()


def calculate_checksum(file_path: Path) -> str:
    """Calculate the checksum of a file."""
    hash_md5 = hashlib.md5()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def resize_image(file_path: Path, max_size: tuple[int, int], quality=40):
    """Resize an image."""
    with Image.open(file_path) as img:
        if max_size:
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Resampling.LANCZOS)
        img.save(file_path, quality=quality, optimize=True)


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
