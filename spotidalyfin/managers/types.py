from datetime import datetime
from enum import Enum
from typing import Self

import tidalapi
from tidalapi.exceptions import MetadataNotAvailable

from spotidalyfin.utils.comparisons import close, weighted_word_overlap
from spotidalyfin.utils.formatting import parse_date


class Platform(Enum):
    TIDAL = "TIDAL"
    SPOTIFY = "SPOTIFY"
    JELLYFIN = "JELLYFIN"


class TrackQuality(Enum):
    DOLBY_ATMOS = 0
    LOW = 1
    LOSSLESS = 2
    HI_RES_LOSSLESS = 3


class Artist:
    def __init__(self, platform: Platform, name: str, artist_id: str | int, genres: list = list):
        self.platform = platform
        self.name = name
        self.artist_id = str(artist_id).lower()
        self.genres = genres

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, Artist):
            return self.artist_id == other.artist_id and self.name == other.name
        return False


class Album:
    def __init__(self, platform: Platform, name: str, artists: list[Artist], release_date: datetime, tracks: list,
                 album_id: str | int, barcode: str | int):
        self.platform = platform
        self.name = name
        self.artists = artists
        self.release_date = release_date
        self.tracks = tracks
        self.album_id = str(album_id).lower()
        self.barcode = str(barcode).lower()

    def __str__(self):
        return f"{self.name} by {self.artists[0]} released on {self.release_date.date()}"

    def __eq__(self, other):
        if isinstance(other, Album):
            return (self.album_id == other.album_id and
                    self.name == other.name and
                    self.artists == other.artists and
                    # self.release_date == other.release_date and # sometimes release date isn't filled in
                    self.tracks == other.tracks)
        return False


class Track:
    def __init__(self, platform: Platform, name: str, artist: Artist, album: Album, duration: int, artists: list,
                 isrc: str = None, track_id: str = None, lyrics: str = None, quality: TrackQuality = None):
        self.platform = platform
        self.name = name
        self.artist = artist
        self.album = album
        self.duration = duration
        self.artists = artists
        self.isrc = isrc.lower()
        self.id = track_id
        self.lyrics = lyrics
        self.quality = quality

    def __str__(self):
        return f"{self.name} by {self.artist} from {self.album.name}"

    def __eq__(self, other):
        if isinstance(other, Track):
            return (self.id == other.id
                    and self.name == other.name
                    and self.artist == other.artist
                    and self.album == other.album
                    and self.duration == other.duration
                    and self.artists == other.artists
                    and self.isrc == other.isrc
                    and self.platform == other.platform)
        return False

    def matches(self, other: Self) -> bool:
        if not isinstance(other, Track):
            return False

        score = 0

        if close(self.duration, other.duration):
            score += 1
        if self.isrc == other.isrc:
            score += 0.5
        if weighted_word_overlap(self.name, other.name) > 0.7:
            score += 1
        if weighted_word_overlap(self.album.name, other.album.name) > 0.35:
            score += 1.5

        same_artists = True
        for artist in other.artists:
            if artist not in self.artists:
                same_artists = False
        if same_artists:
            score += 1


class Playlist:
    def __init__(self, platform: Platform, name: str, image: str, playlist_id: str, tracks: list[Track] = list):
        self.platform = platform
        self.name = name
        self.image = image
        self.playlist_id = playlist_id
        self.tracks = tracks

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, Playlist):
            return self.playlist_id == other.playlist_id and self.name == other.name and self.image == other.image and self.tracks == other.tracks
        return False

    def load_tracks(self, tracks: list[Track]):
        self.tracks = tracks


def track_from_spotify_track(spotify_track: dict) -> Track:
    return Track(
        platform=Platform.SPOTIFY,
        name=spotify_track['name'],
        artist=artist_from_spotify_artist(spotify_track['artists'][0]),
        album=album_from_spotify_album(spotify_track['album']),
        duration=int(spotify_track['duration_ms'] / 1000),
        artists=[artist_from_spotify_artist(artist) for artist in spotify_track['artists']],
        isrc=spotify_track['external_ids'].get('isrc'),
        track_id=spotify_track['id']
    )


def track_from_tidal_track(tidal_track: tidalapi.Track) -> Track:
    def real_quality(track: tidalapi.Track) -> TrackQuality:
        """The audio_quality parameter isn't always correct"""
        if track.is_dolby_atmos:
            return TrackQuality.DOLBY_ATMOS
        elif track.is_hi_res_lossless:
            return TrackQuality.HI_RES_LOSSLESS
        elif track.is_lossless:
            return TrackQuality.LOSSLESS
        else:
            return TrackQuality.LOW

    def lyrics(track: tidalapi.Track) -> str:
        try:
            result = track.lyrics()
            return result.subtitles or result.text
        except MetadataNotAvailable | KeyError:
            return ""

    return Track(
        platform=Platform.TIDAL,
        name=tidal_track.full_name,
        artist=artist_from_tidal_artist(tidal_track.artist),
        album=album_from_tidal_album(tidal_track.album),
        duration=tidal_track.duration,
        artists=[artist_from_tidal_artist(artist) for artist in tidal_track.artists],
        isrc=tidal_track.isrc,
        track_id=tidal_track.id,
        quality=real_quality(tidal_track),
        lyrics=lyrics(tidal_track)
    )


def album_from_spotify_album(spotify_album) -> Album:
    return Album(
        platform=Platform.SPOTIFY,
        name=spotify_album['name'],
        artists=[artist_from_spotify_artist(artist) for artist in spotify_album['artists']],
        release_date=parse_date(spotify_album['release_date']),
        tracks=[None for _ in range(spotify_album['total_tracks'])],
        album_id=spotify_album['id'],
        barcode=spotify_album['external_ids']['upc'] or None
    )


def album_from_tidal_album(tidal_album: tidalapi.Album, load_tracks: bool = False) -> Album:
    if load_tracks:
        tracks = tidal_album.tracks()
    else:
        tracks = [None for _ in range(tidal_album.num_tracks)] if tidal_album.num_tracks else []

    return Album(
        platform=Platform.TIDAL,
        name=tidal_album.name,
        artists=[artist_from_tidal_artist(artist) for artist in tidal_album.artists],
        release_date=tidal_album.release_date,
        tracks=tracks,
        album_id=tidal_album.id,
        barcode=tidal_album.universal_product_number
    )


def artist_from_spotify_artist(spotify_artist) -> Artist:
    return Artist(
        platform=Platform.SPOTIFY,
        name=spotify_artist['name'],
        artist_id=spotify_artist['id'],
        genres=spotify_artist.get('genres', [])
    )


def artist_from_tidal_artist(tidal_artist: tidalapi.Artist) -> Artist:
    return Artist(
        platform=Platform.TIDAL,
        name=tidal_artist.name,
        artist_id=tidal_artist.id
    )
