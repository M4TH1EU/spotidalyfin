from dataclasses import dataclass, field
from typing import List, Optional

from ..managers.types import Platform

@dataclass
class PlatformBound:
    platform: Platform = field(init=False)

    def __post_init__(self):
        self.platform = self.__class__.PLATFORM


@dataclass
class Playlist:
    platform: Platform
    id: str
    name: str
    description: Optional[str] = None
    tracks: List['Track'] = field(default_factory=list)
    image: str = ""


@dataclass
class SpotifyPlaylist(PlatformBound, Playlist):
    PLATFORM = Platform.SPOTIFY


@dataclass
class TidalPlaylist(PlatformBound, Playlist):
    PLATFORM = Platform.TIDAL


@dataclass
class FavoriteTracksPlaylist(Playlist):
    id: str = field(init=False, default="favorite_tracks")


@dataclass
class SpotifyFavoriteTracksPlaylist(PlatformBound, FavoriteTracksPlaylist):
    PLATFORM = Platform.SPOTIFY


@dataclass
class TidalFavoriteTracksPlaylist(PlatformBound, FavoriteTracksPlaylist):
    PLATFORM = Platform.TIDAL