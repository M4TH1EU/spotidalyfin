from datetime import datetime
from enum import Enum
from typing import Self

import requests
import tidalapi
from tidalapi.exceptions import MetadataNotAvailable
from tidalapi.media import StreamManifest

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


class Metadata:
    def __init__(self, title: str = "", album: str = "", albumartist: str = "", artist: str = "", copy_right: str = "",
                 tracknumber: int = 1,
                 discnumber: int = 1, totaldiscs: int = 1, totaltracks: int = 1, date: datetime = datetime.now(),
                 isrc: str = "", lyrics: str = "", cover_url: str = "",
                 spotify_id: str = "", tidal_id: str = ""):
        self.title = title
        self.album = album
        self.albumartist = albumartist
        self.artist = artist
        self.copy_right = copy_right
        self.tracknumber = tracknumber
        self.discnumber = discnumber
        self.totaldiscs = totaldiscs
        self.totaltracks = totaltracks
        self.date = date.strftime("%Y-%m-%d")
        self.isrc = isrc
        self.lyrics = lyrics
        self.cover_url = cover_url
        self.spotify_id = spotify_id
        self.tidal_id = tidal_id


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
                 album_id: str | int, barcode: str | int, cover_url: str = None, num_volumes: int = None):
        self.platform = platform
        self.name = name
        self.artists = artists
        self.release_date = release_date
        self.tracks = tracks
        self.album_id = str(album_id).lower()
        self.barcode = str(barcode).lower()
        self.cover_url = cover_url
        self.num_volumes = num_volumes

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
                 isrc: str = None, track_id: str = None, lyrics: str = None, quality: TrackQuality = None,
                 stream_manifest: StreamManifest = None, copyright: str = None, track_number: int = None,
                 disc_number: int = None, release_date: datetime = None, cover_url: str = None):
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
        self.stream_manifest = stream_manifest
        self.copyright = copyright
        self.track_number = track_number
        self.disc_number = disc_number
        self.release_date = release_date
        self.cover_url = cover_url

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

    def metadata(self) -> Metadata:
        return Metadata(
            title=self.name,
            album=self.album.name,
            albumartist=self.album.artists[0].name,
            artist=self.artist.name,
            copy_right=self.copyright,
            tracknumber=self.track_number,
            discnumber=self.disc_number,
            totaldiscs=self.album.num_volumes,
            totaltracks=len(self.album.tracks),
            date=self.release_date,
            isrc=self.isrc,
            lyrics=self.lyrics,
            cover_url=self.cover_url
        )

    def matches(self, other: Self) -> bool:
        """Check if two tracks object represent the same track regardless of the platform"""
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

        other.score = score

        return score >= 3.5

    def download(self) -> bytes:
        if self.platform == Platform.SPOTIFY:
            raise NotImplementedError("Downloading from Spotify is not supported")
        elif self.platform == Platform.TIDAL:
            download_urls = self.stream_manifest.get_urls()
            mimetype = self.stream_manifest.mime_type.split("/")[-1]

            bytes_response = b""
            for url in download_urls:
                response = requests.get(url, stream=True, timeout=10)
                response.raise_for_status()
                bytes_response += response.content

            return bytes_response


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
        name=spotify_track.get('name'),
        artist=artist_from_spotify_artist(spotify_track.get('artists')[0]),
        album=album_from_spotify_album(spotify_track.get('album')),
        duration=int(spotify_track.get('duration_ms', 0) / 1000),
        artists=[artist_from_spotify_artist(artist) for artist in spotify_track.get('artists', [])],
        isrc=spotify_track.get('external_ids', {}).get('isrc'),
        track_id=spotify_track.get('id'),
        cover_url=spotify_track.get('album', {}).get('images', [{}])[0].get('url'),
        track_number=spotify_track.get('track_number'),
        disc_number=spotify_track.get('disc_number'),
        release_date=parse_date(spotify_track.get('album', {}).get('release_date'))
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
        except MetadataNotAvailable:
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
        # lyrics=lyrics(tidal_track), # really slow
        stream_manifest=tidal_track.get_stream().get_stream_manifest(),
        copyright=tidal_track.copyright,
        track_number=tidal_track.track_num,
        disc_number=tidal_track.volume_num,
        release_date=tidal_track.tidal_release_date,
        cover_url=tidal_track.album.image(1280)
    )


def album_from_spotify_album(spotify_album: dict) -> Album:
    return Album(
        platform=Platform.SPOTIFY,
        name=spotify_album.get('name', ''),
        artists=[artist_from_spotify_artist(artist) for artist in spotify_album.get('artists', [])],
        release_date=parse_date(spotify_album.get('release_date')),
        tracks=[None for _ in range(spotify_album.get('total_tracks', 0))],
        album_id=spotify_album.get('id'),
        barcode=spotify_album.get('external_ids', {}).get('upc')
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
        name=spotify_artist.get('name', ''),
        artist_id=spotify_artist.get('id', ''),
        genres=spotify_artist.get('genres', [])
    )


def artist_from_tidal_artist(tidal_artist: tidalapi.Artist) -> Artist:
    return Artist(
        platform=Platform.TIDAL,
        name=tidal_artist.name,
        artist_id=tidal_artist.id
    )
