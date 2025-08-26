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
    artists: list['Artist']
    album: 'Album'
    isrc: Optional[str] = None
    track_number: Optional[int] = None
    vol_number: Optional[int] = None
    replay_gain: Optional[float] = None
    peak_amplitude: Optional[float] = None
    duration: Optional[int] = None
    quality: Optional[TrackQuality] = None
    musicbrainz_recording_id: Optional[str] = None
    musicbrainz_track_id: Optional[str] = None
    musicbrainz_release_artist_id: Optional[list[str]] = None
    musicbrainz_release_group_id: Optional[str] = None
    musicbrainz_artist_id: Optional[list[str]] = None
    musicbrainz_release_id: Optional[str] = None


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
