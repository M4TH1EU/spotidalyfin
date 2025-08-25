from pathlib import Path

from unidecode import unidecode

from syncphony.types import Track


def generate_path(track: Track, base_path: Path, extension: str = "flac") -> Path:
    """
    Generate a sanitized file path based on metadata.
    """
    # Format track number with leading zeros
    track_number_str = f"{int(track.track_number):02}" if track.track_number else "00"

    # Sanitize strings to avoid invalid characters in file paths
    # def sanitize(value: str) -> str:
    #     return "".join(c if c.isalnum() or c in " _-()" else "_" for c in value)

    sanitized_albumartist = unidecode(track.album.artist.name or "Unknown Artist")
    sanitized_album = unidecode(track.album.name or "Unknown Album")
    sanitized_title = unidecode(track.name or "Untitled")

    # Construct the path: base_dir/AlbumArtist/Album/TrackNumber - Title
    return base_path / sanitized_albumartist / sanitized_album / f"{track_number_str} - {sanitized_title}.{extension}"
