import base64
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from PIL import Image
from PIL.Image import Resampling

from spotidalyfin.utils.logger import log


def file_to_list(file_path: Path) -> list:
    """Read a file and return its lines as a list."""
    if not file_path.exists():
        return []

    with open(file_path, 'r') as file:
        return [line.split("#", maxsplit=1)[0].strip() for line in file.readlines() if line.strip()]


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


def create_file(file_path: Path) -> Path:
    """Create a file if it does not exist."""
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()
        log.debug(f"Created file {file_path}")
    return file_path


def move_file(file_path: Path, destination: Path):
    """Move a file to a destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(file_path, destination)
    log.debug(f"Moved {file_path} to {destination}")


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


def get_as_base64(url: str) -> bytes:
    """Get a URL content as base64. Useful for images."""
    try:
        return base64.b64encode(requests.get(url).content)
    except requests.RequestException:
        log.warning(f"Failed to get base64 from {url}")
        return b""


def convert_m4a_bytes_to_flac(input_bytes: bytes, timeout=10, reencode_flac: bool = False) -> bytes:
    """
    Convert an M4A byte stream with a FLAC audio stream to a FLAC byte stream.

    Args:
        input_bytes (bytes): Input M4A data as a byte array.
        timeout (int): Timeout for the conversion process.
        reencode_flac (bool): Whether to re-encode the FLAC audio stream instead of copying it (ffmpeg option)

    Returns:
        bytes: Output FLAC data as a byte array.
    """
    try:
        # Run FFmpeg with stdin (input) and stdout (output)
        process = subprocess.run(
            [
                "ffmpeg",
                "-i", "pipe:0",  # Use pipe as input (stdin)
                "-f", "flac",  # Specify output format as FLAC
                "-c:a", "copy" if not reencode_flac else "flac", # Copy audio codec (no re-encoding it's already FLAC inside M4A)
                "pipe:1"  # Use pipe as output (stdout)
            ],
            input=input_bytes,  # Provide the byte array as input
            stdout=subprocess.PIPE,  # Capture stdout for the FLAC output
            stderr=subprocess.PIPE,  # Capture errors for debugging
            timeout=timeout
        )

        # Check if FFmpeg succeeded
        if process.returncode != 0:
            raise subprocess.SubprocessError(f"FFmpeg error: {process.stderr.decode()}")

        return process.stdout  # Return FLAC audio as bytes
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg process timed out")
    except subprocess.SubprocessError as e:
        if not reencode_flac:
            log.debug("Failed to convert M4A to FLAC. Trying to re-encode in FLAC instead of copy...")
            return convert_m4a_bytes_to_flac(input_bytes, timeout, reencode_flac=True)
        else:
            raise RuntimeError(f"Error during FFmpeg conversion: {e}")


def replace_m4a_by_flac(file_path: Path, timeout=25) -> Path:
    """
    Convert an M4A file to a FLAC file and replace the original file. Returns the new FLAC file path.
    The original M4A file is deleted. This operation is irreversible!

    Args:
        file_path (Path): Path to the M4A file.
        timeout (int): Timeout for the conversion process.

    Returns:
        Path: Path to the new FLAC file.
    """
    m4a_bytes = file_path.read_bytes()
    flac_bytes = convert_m4a_bytes_to_flac(m4a_bytes, timeout)

    new_path = file_path.with_suffix(".flac")
    new_path.write_bytes(flac_bytes)

    file_path.unlink()

    return new_path


def get_size_of_folder(folder: Path) -> int:
    """Get the size of a folder in bytes."""
    return sum(file.stat().st_size for file in get_all_files_in_directory(folder))
