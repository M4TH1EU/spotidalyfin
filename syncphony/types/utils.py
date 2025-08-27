import base64
import tempfile
from typing import Optional

import requests

from syncphony.types import Track, Album
from syncphony.utils.compare import compare_tracks, compare_albums
from syncphony.types.enums import MatchType
from syncphony.types.manager import Manager
from syncphony.utils.logger import syncphony_logger


def get_track_on_another_platform(track: Track, manager: Manager) -> Optional[Track]:
    if track.platform == manager.PLATFORM:
        return track

    results = manager.search_tracks_from_track(track)
    if not results:
        return None

    # Build a list of (track, score)
    scored_results = [(t, compare_tracks(track, t)) for t in results]
    best_match, best_score = max(scored_results, key=lambda x: x[1], default=(None, 0))

    if best_match and best_score >= 75.0:
        manager.save_match_to_db(src_id=track.id, src_platform=track.platform,
                                 dest_id=best_match.id, type=MatchType.TRACK)
        return best_match

    return None


def get_tracks_on_another_platform(tracks: list[Track], manager: Manager) -> list[Track]:
    """Get tracks on another platform."""
    return [get_track_on_another_platform(track, manager) for track in tracks if track.platform != manager.PLATFORM]


def get_album_on_another_platform(album: Album, manager: Manager) -> Optional[Album]:
    if album.platform == manager.PLATFORM:
        return album

    results = manager.search_albums(query=f"{album.name}", upc=album.barcode)
    if not results:
        return None

    # Build a list of (album, score)
    scored_results = [(a, compare_albums(album, a)) for a in results]
    best_match, best_score = max(scored_results, key=lambda x: x[1], default=(None, 0))

    if best_match and best_score >= 75.0:
        manager.save_match_to_db(src_id=album.id, src_platform=album.platform,
                                 dest_id=best_match.id, type=MatchType.ALBUM)
        return best_match

    return None


def get_albums_on_another_platform(albums: list[Album], manager: Manager) -> list[Album]:
    """Get albums on another platform."""
    return [get_album_on_another_platform(album, manager) for album in albums if album.platform != manager.PLATFORM]


def open_image_url(url: str, logger=syncphony_logger) -> Optional[bytes]:
    # TODO: is this needed or can get_as_base64 be used? possible to stay in-memory?
    """Open an image URL and return the image data."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile() as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
            f.seek(0)
            return f.read()
    except requests.RequestException:
        logger.error(f"Failed to open image URL {url}")
        return None


def get_as_base64(url: str, logger=syncphony_logger) -> bytes:
    """Get a URL content as base64. Useful for images."""
    try:
        return base64.b64encode(requests.get(url).content)
    except requests.RequestException:
        logger.error(f"Failed to get base64 from {url}")
        return b""
