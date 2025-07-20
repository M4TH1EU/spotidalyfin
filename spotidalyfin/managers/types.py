from __future__ import annotations  # For forward type references in Python < 3.10

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import acoustid
import musicbrainzngs
import requests
from mutagen.flac import FLAC, Picture
from mutagen.id3 import TALB, TCOP, TDRC, TIT2, TOPE, TPE1, TRCK, TSRC, USLT, ID3, APIC
from mutagen.mp3 import MP3
from tidalapi import Role
from tidalapi.media import StreamManifest, AudioExtensions
from unidecode import unidecode

from spotidalyfin.models.enums import Platform, TrackQuality
from spotidalyfin.utils.comparisons import weighted_word_overlap
from spotidalyfin.utils.file_utils import open_image_url
from spotidalyfin.utils.logger import log


#
# THIS ISN'T USED ANYMORE AND IS HERE ONLY FOR REFERENCE UNTIL MIGRATED TO NEW FILES
#

def _generate_artists_string(artists: list[Artist]) -> str:
    output = ""
    for artist in artists:
        if artist.role == Role.main:
            output += f"{artist.name} "
        elif artist.role == Role.featured:
            if "feat." not in output:
                output += f"feat. {artist.name} "
            else:
                output += f"& {artist.name} "  # If there are multiple featured artists

    return output.strip()


def get_acoustid_fingerprint(file: Path) -> str:
    """Query AcoustID for metadata based on the audio file."""
    duration, fingerprint = acoustid.fingerprint_file(file)
    duration = 170
    print(f"Fingerprint: {fingerprint}, Duration: {duration}")

    res = acoustid.lookup("YjwCJxwC0r", fingerprint, duration)  # public key for testing, please don't abuse

    return res['results'][0]['id'] if res['results'] else ""


def query_musicbrainz(irsc: str) -> dict:
    """Query MusicBrainz for additional metadata based on the ISRC."""
    musicbrainzngs.set_useragent("spotidalyfin", "0.1")
    try:
        result: dict = musicbrainzngs.get_recordings_by_isrc(irsc, includes=["artists", "releases"])
    except Exception as e:
        log.error(f"No results found for ISRC {irsc} on MusicBrainz: {e}")
        return {}

    if not result.get("isrc", {}).get("recording-list"):
        return {}

    artist_ids = []
    for artist in result.get('isrc', {}).get('recording-list', [{}])[0].get('artist-credit', []):
        # TOOD: investigate why when artist is a string and it causes an AtributeError it is not caught by the except
        # and just skips the rest of the metadata writing in download_track ???
        if isinstance(artist, str):
            continue

        if artist.get('artist', {}).get('id'):
            artist_ids.append(artist.get('artist', {}).get('id'))

    return {
        "MUSICBRAINZ_TRACKID": result.get("isrc", {}).get("recording-list", [{}])[0].get("id"),
        "MUSICBRAINZ_ALBUMID": result.get("isrc", {}).get("recording-list", [{}])[0].get("release-list", [{}])[0].get(
            "id"),
        "BARCODE": result.get("isrc", {}).get("recording-list", [{}])[0].get("release-list", [{}])[0].get("barcode"),
        "MUSICBRAINZ_ARTISTID": artist_ids,
        "MUSICBRAINZ_ALBUMARTISTID": artist_ids,
        "DATE": result.get("isrc", {}).get("recording-list", [{}])[0].get("release-list", [{}])[0].get("date"),
        "ORIGINALDATE": result.get("isrc", {}).get("recording-list", [{}])[0].get("release-list", [{}])[0].get("date"),
        "ORIGINALYEAR": result.get("isrc", {}).get("recording-list", [{}])[0].get("release-list", [{}])[0].get("date")[
                        :4],
    }


@dataclass
class Metadata:
    track: Track

    def write_to_file(self, path: Path) -> None:
        """Write metadata to a FLAC, M4A or MP3 file."""
        if not path.exists():
            raise FileNotFoundError(f"File {path} does not exist")

        extension = path.suffix.lower()
        if "flac" in extension:
            self._write_flac_metadata(path)
        elif "m4a" in extension:
            # self._write_m4a_metadata(path)
            raise NotImplementedError("M4A metadata writing is not supported yet.")
        elif "mp3" in extension:
            self._write_mp3_metadata(path)
        else:
            raise ValueError(f"Unsupported file format: {extension}")

    # TODO: Implement M4A metadata writing (not perfect yet (isrc/cover))
    # def _write_m4a_metadata(self, path: Path) -> None:
    #     """Write metadata to a M4A file."""
    #     audio = MP4(path)
    #     tags = MP4Tags()
    #     tags["\xa9nam"] = self.title or "Untitled"
    #     tags["\xa9alb"] = self.album or "Unknown Album"
    #     tags["\xa9ART"] = self.artist or self.albumartist or "Unknown Artist"
    #     tags["aART"] = self.albumartist or "Unknown Artist"
    #     tags["cprt"] = self.copy_right or ""
    #     tags["trkn"] = [(self.tracknumber or 1, self.totaltracks or 1)]
    #     tags["disk"] = [(self.discnumber or 1, self.totaldiscs or 1)]
    #     tags["\xa9day"] = self.date.strftime("%Y-%m-%d") if self.date else ""
    #     audio['\xa9isrc'] = self.isrc or ""
    #     # audio["----:com.apple.iTunes:ISRC"] = [self.isrc or ""]
    #     audio["\xa9lyr"] = self.lyrics or ""
    #     if self.spotify_id:
    #         audio["spotify_id"] = self.spotify_id
    #     if self.tidal_id:
    #         audio["tidal_id"] = self.tidal_id
    #     audio["covr"] = [
    #         MP4Cover(open_image_url(self.cover_url), imageformat=MP4Cover.FORMAT_JPEG if self.cover_url.endswith(
    #             ".jpg") else MP4Cover.FORMAT_PNG)]
    #     audio.tags = tags
    #     audio.save()

    def _write_flac_metadata(self, path: Path) -> None:
        """Write metadata to a FLAC file."""

        audio = FLAC(path)
        audio.clear()  # Clear existing tags
        audio["title"] = self.track.name or "Untitled"
        audio["album"] = self.track.album.name or "Unknown Album"
        audio["albumartist"] = _generate_artists_string(self.track.album.artists) or "Unknown Artist"
        audio["albumartistsort"] = audio["albumartist"]
        audio["barcode"] = ""  # TODO: Add barcode
        audio["artist"] = _generate_artists_string([self.track.artist]) or "Unknown Artist"
        audio["artistsort"] = _generate_artists_string(self.track.artists) or "Unknown Artist"
        audio["artists"] = [x.name for x in self.track.artists]
        audio["copy_right"] = self.track.copyright or ""
        audio["tracknumber"] = str(self.track.track_number) or "1"
        audio["discnumber"] = str(self.track.disc_number) or "1"
        audio["totaldiscs"] = str(self.track.album.num_volumes) or "1"
        audio["totaltracks"] = str(len(self.track.album.tracks)) or "1"
        audio["date"] = self.track.release_date.strftime("%Y-%m-%d") if self.track.release_date else ""
        audio["originaldate"] = audio["date"]
        audio["originalyear"] = self.track.release_date.strftime("%Y") if self.track.release_date else ""
        audio["isrc"] = self.track.isrc or ""
        audio["lyrics"] = self.track.lyrics or ""

        if self.track.isrc:  # TODO: add option to disable this
            for k, v in query_musicbrainz(self.track.isrc).items():
                if v:
                    audio[k] = v

        # Add cover art
        if self.track.cover_url:
            cover = Picture()
            cover.type = 3  # Front cover
            cover.mime = "image/jpeg" if self.track.cover_url.endswith(".jpg") else "image/png"
            cover.desc = "front cover"
            cover.data = open_image_url(self.track.cover_url)
            audio.add_picture(cover)

        audio.save()

    def _write_mp3_metadata(self, path: Path) -> None:
        """Write metadata to an MP3 file."""
        audio = MP3(path, ID3=ID3)
        audio.delete()  # Clear existing tags

        audio.tags.add(TIT2(encoding=3, text=self.track.name))  # Title
        audio.tags.add(TALB(encoding=3, text=self.track.album.name))  # Album
        audio.tags.add(TPE1(encoding=3, text=self.track.artist.name))  # Artist
        audio.tags.add(TOPE(encoding=3, text=self.track.album.artists[0].name))  # Album Artist
        audio.tags.add(TCOP(encoding=3, text=self.track.copyright))  # Copyright
        audio.tags.add(TRCK(encoding=3, text=str(self.track.track_number)))  # Track Number
        audio.tags.add(
            TDRC(encoding=3, text=self.track.release_date.strftime("%Y-%m-%d") if self.track.release_date else ""))
        audio.tags.add(TSRC(encoding=3, text=self.track.isrc))
        audio.tags.add(USLT(encoding=3, text=self.track.lyrics))  # Lyrics

        # Add cover art
        if self.track.cover_url:
            audio.tags.add(APIC(
                encoding=3,
                mime="image/jpeg" if self.track.cover_url.endswith(".jpg") else "image/png",
                type=3,  # Cover art
                desc="Cover",
                data=open_image_url(self.track.cover_url)
            ))

        audio.save()

    def generate_path(self, base_path: Path, extension: str = "flac") -> Path:
        """
        Generate a sanitized file path based on metadata.
        """
        # Format track number with leading zeros
        track_number_str = f"{int(self.track.track_number):02}" if self.track.track_number else "00"

        # Sanitize strings to avoid invalid characters in file paths
        # def sanitize(value: str) -> str:
        #     return "".join(c if c.isalnum() or c in " _-()" else "_" for c in value)

        sanitized_albumartist = unidecode(self.track.album.artists[0].name or "Unknown Artist")
        sanitized_album = unidecode(self.track.album.name or "Unknown Album")
        sanitized_title = unidecode(self.track.name or "Untitled")

        # Construct the path: base_dir/AlbumArtist/Album/TrackNumber - Title
        return base_path / sanitized_albumartist / sanitized_album / f"{track_number_str} - {sanitized_title}.{extension}"


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
    download_urls: Optional[List[str]] = None
    file_extension: Optional[str] = None
    copyright: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    release_date: Optional[datetime] = None
    cover_url: Optional[str] = None
    score: Optional[float] = None

    def matches(self, other: Track) -> (bool, float):
        """
        Checks if two Track objects represent the same track across engines.

        Scoring criteria:
        - Duration similarity
        - ISRC match
        - Title and album name similarity
        - Artist overlap

        Returns:
            bool: True if the tracks are considered a match, False otherwise.
            float: The match score as a float between
        """
        if not isinstance(other, Track):
            return False

        score = 0
        if abs(self.duration - other.duration) <= 2:  # Allow a slight variation in duration
            score += 1
        if self.isrc and self.isrc == other.isrc:
            score += 2
        if weighted_word_overlap(self.name, other.name) > 0.7:
            score += 1
        if weighted_word_overlap(self.album.name, other.album.name) > 0.35:
            score += 1.5
        if other.album.name == self.name:  # If the album name is the same as the track name (e.g. singles)
            score += 0.5
        if all(artist in self.artists for artist in other.artists):
            score += 1

        # Save the score in the other track for reference
        other.score = score

        return score >= 3.5, score

    def raw_data(self, retry_count=3) -> (bytes, str):
        """
        Downloads the track's audio file based on the platform and manifest.

        Returns:
            bytes: The audio file as a byte stream.
            str: The file extension of the audio file.

        Raises:
            DownloadTrackException: If the download fails.
        """

        def _download():
            if self.platform == Platform.SPOTIFY:
                raise NotImplementedError("Downloading from Spotify is not supported.")
            elif self.platform == Platform.TIDAL:
                if not self.stream_manifest:
                    raise ValueError("Stream manifest is missing.")
                download_urls = self.stream_manifest.get_urls()

                match self.stream_manifest.file_extension:
                    case AudioExtensions.M4A:
                        file_extension = "m4a"
                    case AudioExtensions.FLAC:
                        file_extension = "flac"
                    case AudioExtensions.MP4:
                        raise ValueError("Video files are not supported.")
                    case _:
                        raise ValueError(f"Unsupported file extension: {self.stream_manifest.file_extension}")

                # Use bytearray for efficient byte concatenation
                bytes_response = bytearray()

                for url in download_urls:
                    response = requests.get(url, stream=True, timeout=30)
                    response.raise_for_status()
                    bytes_response.extend(response.content)

                return bytes(bytes_response), file_extension
            else:
                raise NotImplementedError(f"Downloading is not supported for {self.platform}.")

        try:
            return _download()
        except Exception as e:
            if retry_count <= 0:
                # log.exception(f"Download failed: {e}")
                raise Exception(f"Download failed for track {self.name} by {self.artist.name} : {e}")
            else:
                log.warning(
                    f"Download failed for track {self.name} by {self.artist.name}. Retrying {retry_count} more times. Error: {e}")
                return self.raw_data(retry_count - 1)
