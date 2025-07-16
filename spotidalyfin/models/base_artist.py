from dataclasses import dataclass, field
from typing import List, Optional

from .enums import ArtistRole


@dataclass
class Artist:
    name: str
    id: str
    genres: List[str] = field(default_factory=list)
    role: ArtistRole = ArtistRole.ARTIST
    image: Optional[str] = None

@dataclass
class SpotifyArtist(Artist):
    pass