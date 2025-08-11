from dataclasses import dataclass, field
from typing import List, Optional

from syncphony.models.enums import Platform


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
    image: Optional[bytes] = None


@dataclass
class SpotifyPlaylist(PlatformBound, Playlist):
    PLATFORM = Platform.SPOTIFY


@dataclass
class TidalPlaylist(PlatformBound, Playlist):
    PLATFORM = Platform.TIDAL


@dataclass
class JellyfinPlaylist(PlatformBound, Playlist):
    PLATFORM = Platform.JELLYFIN


@dataclass
class FavoriteTracksPlaylist(Playlist):
    id: str = field(init=False, default="favorite_tracks")


@dataclass
class SpotifyFavoriteTracksPlaylist(PlatformBound, FavoriteTracksPlaylist):
    PLATFORM = Platform.SPOTIFY


@dataclass
class TidalFavoriteTracksPlaylist(PlatformBound, FavoriteTracksPlaylist):
    PLATFORM = Platform.TIDAL


@dataclass
class JellyfinFavoriteTracksPlaylist(PlatformBound, FavoriteTracksPlaylist):
    PLATFORM = Platform.JELLYFIN

@dataclass
class SubsonicFavoriteTracksPlaylist(PlatformBound, FavoriteTracksPlaylist):
    PLATFORM = Platform.SUBSONIC

@dataclass
class SubsonicPlaylist(PlatformBound, Playlist):
    PLATFORM = Platform.SUBSONIC
