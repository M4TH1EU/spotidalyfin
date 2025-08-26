import datetime
from dataclasses import dataclass, field
from typing import Optional, List

from syncphony.types.enums import Platform


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
    artists: List['Artist']
    barcode: Optional[str] = None
    release_date: Optional[datetime.datetime] = None
    cover: Optional[bytes] = None
    tracks: Optional[List['Track']] = None
    duration: Optional[int] = None
    num_tracks: Optional[int] = None
    num_volumes: Optional[int] = None
    copyright: Optional[str] = None
    replay_gain: Optional[float] = None
    peak_amplitude: Optional[float] = None
    country: Optional[str] = None
    release_status: Optional[str] = None
    genres: Optional[List[str]] = None


@dataclass
class SpotifyAlbum(PlatformBound, Album):
    PLATFORM = Platform.SPOTIFY


@dataclass
class TidalAlbum(PlatformBound, Album):
    PLATFORM = Platform.TIDAL


@dataclass
class JellyfinAlbum(PlatformBound, Album):
    PLATFORM = Platform.JELLYFIN


@dataclass
class SubsonicAlbum(PlatformBound, Album):
    PLATFORM = Platform.SUBSONIC
