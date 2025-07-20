import datetime
from dataclasses import dataclass, field
from typing import Optional, List

from spotidalyfin.models.enums import Platform


@dataclass
class PlatformBound:
    platform: Platform = field(init=False)

    def __post_init__(self):
        self.platform = self.__class__.PLATFORM


@dataclass
class Album:
    platform: Platform
    name: str
    id: str
    artist: 'Artist'
    barcode: Optional[str]
    release_date: Optional[datetime.datetime] = None
    cover_url: Optional[str] = None
    num_volumes: Optional[int] = None
    tracks: Optional[List['Track']] = None


@dataclass
class SpotifyAlbum(PlatformBound, Album):
    PLATFORM = Platform.SPOTIFY


@dataclass
class TidalAlbum(PlatformBound, Album):
    PLATFORM = Platform.TIDAL


@dataclass
class JellyfinAlbum(PlatformBound, Album):
    PLATFORM = Platform.JELLYFIN
