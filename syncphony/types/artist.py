from dataclasses import dataclass, field
from typing import List, Optional

from .enums import ArtistRole, Platform


@dataclass
class PlatformBound:
    platform: Platform = field(init=False)

    def __post_init__(self):
        self.platform = self.__class__.PLATFORM


@dataclass
class Artist:
    platform: Platform
    name: str
    id: str
    role: ArtistRole
    roles: List[ArtistRole]
    genres: Optional[List[str]] = None
    image: Optional[str] = None


@dataclass
class SpotifyArtist(PlatformBound, Artist):
    PLATFORM = Platform.SPOTIFY


@dataclass
class TidalArtist(PlatformBound, Artist):
    PLATFORM = Platform.TIDAL


@dataclass
class JellyfinArtist(PlatformBound, Artist):
    PLATFORM = Platform.JELLYFIN


@dataclass
class SubsonicArtist(PlatformBound, Artist):
    PLATFORM = Platform.SUBSONIC
