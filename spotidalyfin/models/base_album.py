
import datetime
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Album:
    name: str
    id: str
    artist: 'Artist'
    barcode: str
    release_date: Optional[datetime.datetime] = None
    cover_url: Optional[str] = None
    num_volumes: Optional[int] = None
    tracks: Optional[List['Track']] = None

@dataclass
class SpotifyAlbum(Album):
    pass