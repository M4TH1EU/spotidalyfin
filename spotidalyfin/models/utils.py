import base64
from typing import Optional

import requests

from spotidalyfin.models import Track
from spotidalyfin.models.compare import compare_tracks
from spotidalyfin.models.manager import Manager
from spotidalyfin.utils.logger import log


def get_track_on_another_platform(track: Track, manager: Manager) -> Optional[Track]:
    if track.platform == manager.PLATFORM:
        return track

    results = manager.search_tracks(query=track.name, artist_name=track.artist.name if track.artist else None,
                                    isrc=track.isrc)
    if not results:
        return None

    best_match = max(results, key=lambda t: compare_tracks(track, t), default=None)
    return best_match


def get_tracks_on_another_platform(tracks: list[Track], manager: Manager) -> list[Track]:
    """Get tracks on another platform."""
    return [get_track_on_another_platform(track, manager) for track in tracks if track.platform != manager.PLATFORM]


def get_as_base64(url: str) -> bytes:
    """Get a URL content as base64. Useful for images."""
    try:
        return base64.b64encode(requests.get(url).content)
    except requests.RequestException:
        log.warning(f"Failed to get base64 from {url}")
        return b""
