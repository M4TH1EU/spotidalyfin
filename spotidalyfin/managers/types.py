from __future__ import annotations  # For forward type references in Python < 3.10

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List

import requests
import tidalapi
from mutagen.flac import FLAC, Picture
from mutagen.id3 import TALB, TCOP, TDRC, TIT2, TOPE, TPE1, TRCK, TSRC, USLT, ID3, APIC
from mutagen.mp3 import MP3
from tidalapi.exceptions import MetadataNotAvailable
from tidalapi.media import StreamManifest

from spotidalyfin.utils.comparisons import weighted_word_overlap
from spotidalyfin.utils.file_utils import open_image_url
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


@dataclass
class Metadata:
    title: str = ""
    album: str = ""
    albumartist: str = ""
    artist: str = ""
    copy_right: str = ""
    tracknumber: int = 1
    discnumber: int = 1
    totaldiscs: int = 1
    totaltracks: int = 1
    date: Optional[datetime] = field(default_factory=datetime.now)
    isrc: str = ""
    lyrics: str = ""
    cover_url: str = ""
    spotify_id: str = ""
    tidal_id: str = ""

    def write_to_file(self, path: Path) -> None:
        """Write metadata to a FLAC or MP3 file."""
        if not path.exists():
            raise FileNotFoundError(f"File {path} does not exist")

        extension = path.suffix.lower()
        if "flac" in extension:
            self._write_flac_metadata(path)
        elif "mp3" in extension:
            self._write_mp3_metadata(path)
        else:
            raise ValueError(f"Unsupported file format: {extension}")

    def _write_flac_metadata(self, path: Path) -> None:
        """Write metadata to a FLAC file."""
        audio = FLAC(path)
        audio.clear()  # Clear existing tags
        audio["title"] = self.title
        audio["album"] = self.album
        audio["albumartist"] = self.albumartist
        audio["artist"] = self.artist
        audio["copy_right"] = self.copy_right
        audio["tracknumber"] = str(self.tracknumber)
        audio["discnumber"] = str(self.discnumber)
        audio["totaldiscs"] = str(self.totaldiscs)
        audio["totaltracks"] = str(self.totaltracks)
        audio["date"] = self.date.strftime("%Y-%m-%d") if self.date else ""
        audio["isrc"] = self.isrc
        audio["lyrics"] = self.lyrics
        if self.spotify_id:
            audio["spotify_id"] = self.spotify_id
        if self.tidal_id:
            audio["tidal_id"] = self.tidal_id

        # Add cover art
        if self.cover_url:
            cover = Picture()
            cover.type = 3  # Front cover
            cover.mime = "image/jpeg" if self.cover_url.endswith(".jpg") else "image/png"
            cover.desc = "front cover"
            cover.data = open_image_url(self.cover_url)
            audio.add_picture(cover)

        audio.save()

    def _write_mp3_metadata(self, path: Path) -> None:
        """Write metadata to an MP3 file."""
        audio = MP3(path, ID3=ID3)
        audio.delete()  # Clear existing tags

        audio.tags.add(TIT2(encoding=3, text=self.title))  # Title
        audio.tags.add(TALB(encoding=3, text=self.album))  # Album
        audio.tags.add(TPE1(encoding=3, text=self.artist))  # Artist
        audio.tags.add(TOPE(encoding=3, text=self.albumartist))  # Album Artist
        audio.tags.add(TCOP(encoding=3, text=self.copy_right))  # Copyright
        audio.tags.add(TRCK(encoding=3, text=str(self.tracknumber)))  # Track Number
        audio.tags.add(TDRC(encoding=3, text=self.date.strftime("%Y-%m-%d") if self.date else ""))  # Release Date
        audio.tags.add(TSRC(encoding=3, text=self.isrc))  # ISRC
        audio.tags.add(USLT(encoding=3, text=self.lyrics))  # Lyrics

        # Add cover art
        if self.cover_url:
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg" if self.cover_url.endswith(".jpg") else "image/png",
                    type=3,  # Cover art
                    desc="Cover",
                    data=open_image_url(self.cover_url)
                )
            )

        audio.save()

    def generate_path(self, base_path: Path, extension: str = "flac") -> Path:
        """
        Generate a sanitized file path based on metadata.
        """
        # Format track number with leading zeros
        track_number_str = f"{int(self.tracknumber):02}" if self.tracknumber else "00"

        # Sanitize strings to avoid invalid characters in file paths
        def sanitize(value: str) -> str:
            return "".join(c if c.isalnum() or c in " _-()" else "_" for c in value)

        sanitized_albumartist = sanitize(self.albumartist or "Unknown Artist")
        sanitized_album = sanitize(self.album or "Unknown Album")
        sanitized_title = sanitize(self.title or "Untitled")

        # Construct the path: base_dir/AlbumArtist/Album/TrackNumber - Title
        return base_path / sanitized_albumartist / sanitized_album / f"{track_number_str} - {sanitized_title}.{extension}"


@dataclass
class Artist:
    """
    Represents an artist with associated metadata.
    """
    platform: Platform
    name: str
    artist_id: str
    genres: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Normalize artist ID to lowercase
        self.artist_id = str(self.artist_id).lower()

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Artist):
            return False
        return self.artist_id == other.artist_id and self.name == other.name


@dataclass
class Album:
    """
    Represents an album with metadata and associated tracks.
    """
    platform: Platform
    name: str
    artists: List[Artist]
    release_date: Optional[datetime]
    tracks: List[Optional[Track]]
    album_id: str
    barcode: str
    cover_url: Optional[str] = None
    num_volumes: Optional[int] = None

    def __post_init__(self):
        # Normalize album ID and barcode to lowercase strings
        self.album_id = str(self.album_id).lower()
        self.barcode = str(self.barcode).lower()

    def __str__(self) -> str:
        primary_artist = self.artists[0].name if self.artists else "Unknown Artist"
        release_date_str = self.release_date.date() if self.release_date else "Unknown Date"
        return f"{self.name} by {primary_artist} released on {release_date_str}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Album):
            return False
        return (
                self.album_id == other.album_id
                and self.name == other.name
                and self.artists == other.artists
                and self.tracks == other.tracks  # Note: Tracks must implement their own __eq__
        )


@dataclass
class Track:
    """
    Represents a track with associated metadata and utility methods for comparison and download.
    """
    platform: Platform
    name: str
    artist: Artist
    album: Album
    duration: int  # Duration in seconds
    artists: List[Artist]
    isrc: Optional[str] = None
    track_id: Optional[str] = None
    lyrics: Optional[str] = None
    quality: Optional[TrackQuality] = None
    stream_manifest: Optional[StreamManifest] = None
    copyright: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    release_date: Optional[datetime] = None
    cover_url: Optional[str] = None

    def __post_init__(self):
        if self.isrc:
            self.isrc = self.isrc.lower()

    def __str__(self) -> str:
        return f"{self.name} by {self.artist} from {self.album.name}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Track):
            return False
        return (
                self.track_id == other.track_id
                and self.name == other.name
                and self.artist == other.artist
                and self.album == other.album
                and self.duration == other.duration
                and self.artists == other.artists
                and self.isrc == other.isrc
                and self.platform == other.platform
        )

    def metadata(self) -> Metadata:
        """
        Converts track metadata into a Metadata object for further use.
        """
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
            cover_url=self.cover_url,
        )

    def matches(self, other: Track) -> bool:
        """
        Checks if two Track objects represent the same track across platforms.

        Scoring criteria:
        - Duration similarity
        - ISRC match
        - Title and album name similarity
        - Artist overlap
        """
        if not isinstance(other, Track):
            return False

        score = 0
        if abs(self.duration - other.duration) <= 2:  # Allow a slight variation in duration
            score += 1
        if self.isrc and self.isrc == other.isrc:
            score += 0.5
        if weighted_word_overlap(self.name, other.name) > 0.7:
            score += 1
        if weighted_word_overlap(self.album.name, other.album.name) > 0.35:
            score += 1.5
        if all(artist in self.artists for artist in other.artists):
            score += 1

        return score >= 3.5

    def download(self) -> bytes:
        """
        Downloads the track's audio file based on the platform and manifest.

        Returns:
            bytes: The audio file as a byte stream.

        Raises:
            NotImplementedError: If the platform does not support downloading.
            requests.HTTPError: For HTTP-related errors during download.
        """
        if self.platform == Platform.SPOTIFY:
            raise NotImplementedError("Downloading from Spotify is not supported.")
        elif self.platform == Platform.TIDAL:
            if not self.stream_manifest:
                raise ValueError("Stream manifest is missing.")
            download_urls = self.stream_manifest.get_urls()
            mimetype = self.stream_manifest.mime_type.split("/")[-1]

            # Use bytearray for efficient byte concatenation
            bytes_response = bytearray()
            for url in download_urls:
                response = requests.get(url, stream=True, timeout=10)
                response.raise_for_status()
                bytes_response.extend(response.content)

            return bytes(bytes_response)
        else:
            raise NotImplementedError(f"Downloading is not supported for {self.platform}.")


@dataclass
class Playlist:
    """
    Represents a playlist with associated metadata and track list.
    """
    platform: Platform
    name: str
    image: str
    playlist_id: str
    tracks: List[Track] = None

    def __post_init__(self):
        if self.tracks is None:
            self.tracks = []

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Playlist):
            return False
        return (
                self.playlist_id == other.playlist_id
                and self.name == other.name
                and self.image == other.image
                and self.tracks == other.tracks
        )

    def load_tracks(self, tracks: List[Track]) -> None:
        """
        Loads a list of tracks into the playlist.

        Args:
            tracks (List[Track]): The list of tracks to load.
        """
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
        album_id=str(tidal_album.id),
        barcode=str(tidal_album.universal_product_number)
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
        artist_id=str(tidal_artist.id)
    )
