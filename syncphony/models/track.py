from dataclasses import dataclass, field
from typing import Optional

from .enums import TrackQuality, Platform


@dataclass
class PlatformBound:
    platform: Platform = field(init=False)

    def __post_init__(self):
        self.platform = self.__class__.PLATFORM


@dataclass
class Track:
    platform: Platform
    name: str
    id: str
    artist: 'Artist'
    album: 'Album'
    isrc: Optional[str] = None
    track_number: Optional[int] = None
    vol_number: Optional[int] = None
    replay_gain: Optional[int] = None
    replay_peak: Optional[int] = None
    duration: Optional[int] = None
    quality: Optional[TrackQuality] = None


@dataclass
class SpotifyTrack(PlatformBound, Track):
    PLATFORM = Platform.SPOTIFY


@dataclass
class TidalTrack(PlatformBound, Track):
    PLATFORM = Platform.TIDAL


@dataclass
class JellyfinTrack(PlatformBound, Track):
    PLATFORM = Platform.JELLYFIN


@dataclass
class SubsonicTrack(PlatformBound, Track):
    PLATFORM = Platform.SUBSONIC
