from dataclasses import dataclass
from typing import Optional

from .enums import TrackQuality


@dataclass
class Track:
    name: str
    id: str
    artist: 'Artist'  # Forward reference
    album: 'Album'  # Forward reference
    duration: Optional[int] = None
    quality: Optional[TrackQuality] = None

@dataclass
class SpotifyTrack(Track):
    pass