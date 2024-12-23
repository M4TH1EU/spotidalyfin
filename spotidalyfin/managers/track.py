from datetime import datetime
from enum import Enum

from spotidalyfin.utils.formatting import parse_date


class Platform(Enum):
    TIDAL = "TIDAL"
    SPOTIFY = "SPOTIFY"
    JELLYFIN = "JELLYFIN"


class Artist:
    def __init__(self, name: str, artist_id: str):
        self.name = name
        self.artist_id = artist_id

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, Artist):
            return self.artist_id == other.artist_id and self.name == other.name
        return False

    def name(self) -> str:
        return self.name

    def id(self) -> str:
        return self.artist_id


class Album:
    def __init__(self, name: str, artists: list[Artist], release_date: datetime, tracks: list, album_id: str):
        self.name = name
        self.artists = artists
        self.release_date = release_date
        self.tracks = tracks
        self.album_id = album_id

    def __str__(self):
        return f"{self.name} by {self.artists[0]} released on {self.release_date.date()}"

    def __eq__(self, other):
        if isinstance(other, Album):
            return self.album_id == other.album_id and self.name == other.name and self.artists == other.artists and self.release_date == other.release_date and self.tracks == other.tracks
        return False

    def name(self) -> str:
        return self.name

    def artists(self) -> list[Artist]:
        return self.artists

    def release_date(self) -> datetime:
        return self.release_date

    def tracks(self) -> list:
        return self.tracks

    def id(self) -> str:
        return self.album_id


class Track:
    def __init__(self, name: str, artist: Artist, album: Album, duration: int, artists: list, isrc: str = None,
                 platform: Platform = None, track_id: str = None):
        self.name = name
        self.artist = artist
        self.album = album
        self.duration = duration
        self.artists = artists
        self.isrc = isrc
        self.platform = platform
        self.id = track_id

    def __str__(self):
        return f"{self.name} by {self.artist} from {self.album.name}"

    def name(self) -> str:
        return self.name

    def artist(self) -> Artist:
        return self.artist

    def album(self) -> Album:
        return self.album

    def duration(self) -> int:
        return self.duration

    def artists(self) -> list:
        return self.artists

    def isrc(self) -> str:
        return self.isrc

    def platform(self) -> Platform:
        return self.platform

    def id(self) -> str:
        return self.id


def track_from_spotify_track(spotify_track) -> Track:
    return Track(
        name=spotify_track['name'],
        artist=artist_from_spotify_artist(spotify_track['artists'][0]),
        album=album_from_spotify_album(spotify_track['album']),
        duration=int(spotify_track['duration_ms'] / 1000),
        artists=[artist_from_spotify_artist(artist) for artist in spotify_track['artists']],
        isrc=spotify_track['external_ids'].get('isrc'),
        platform=Platform.SPOTIFY,
        track_id=spotify_track['id']
    )


def album_from_spotify_album(spotify_album) -> Album:
    return Album(
        name=spotify_album['name'],
        artists=[artist_from_spotify_artist(artist) for artist in spotify_album['artists']],
        release_date=parse_date(spotify_album['release_date']),
        tracks=[None for _ in range(spotify_album['total_tracks'])],
        album_id=spotify_album['id']
    )


def artist_from_spotify_artist(spotify_artist) -> Artist:
    return Artist(
        name=spotify_artist['name'],
        artist_id=spotify_artist['id']
    )
