import datetime
import hashlib
import random
import string
from typing import List, Optional

import requests

from syncphony.db.database import Database
from syncphony.db.helpers import get_subsonic_login_password, save_subsonic_info_to_db
from syncphony.models.album import SubsonicAlbum
from syncphony.models.artist import SubsonicArtist
from syncphony.models.enums import Platform, TrackQuality
from syncphony.models.manager import Manager
from syncphony.models.playlist import Playlist, SubsonicPlaylist, \
    SubsonicFavoriteTracksPlaylist
from syncphony.models.track import SubsonicTrack
from syncphony.utils.logger import log


def _parse_artist(subsonic_artist: dict) -> SubsonicArtist:
    return SubsonicArtist(
        id=subsonic_artist.get("artistId") or subsonic_artist.get("id"),
        name=subsonic_artist.get("artist") or subsonic_artist.get("name", "Unknown Artist")
    )


def _parse_album(subsonic_album: dict, artist: Optional[SubsonicArtist] = None) -> SubsonicAlbum:
    return SubsonicAlbum(
        id=subsonic_album.get("albumId") or subsonic_album.get("id"),
        name=subsonic_album.get("album") or subsonic_album.get("name", "Unknown Album"),
        artist=artist if artist else _parse_artist(subsonic_album),
        cover=subsonic_album.get("coverArt"),
        barcode="",
        release_date=datetime.datetime(
            subsonic_album.get('originalReleaseDate').get('year', '1970'),
            subsonic_album.get('originalReleaseDate').get('month', 1),
            subsonic_album.get('originalReleaseDate').get('day', 1)
        ) if subsonic_album.get("originalReleaseDate") else subsonic_album.get('year', None),
        num_volumes=None,
        tracks=[_parse_track(_track) for _track in subsonic_album.get("song", [])] if isinstance(
            subsonic_album.get("song"), list) else None
    )


def _parse_track(subsonic_song: dict, artist: Optional[SubsonicArtist] = None,
                 album: Optional[SubsonicAlbum] = None) -> SubsonicTrack:
    return SubsonicTrack(
        id=subsonic_song.get("id"),
        name=subsonic_song.get("title"),
        artist=artist if artist else _parse_artist(subsonic_song),
        album=album if album else _parse_album(subsonic_song, artist),
        isrc=subsonic_song.get("isrc", [""])[0] if isinstance(subsonic_song.get("isrc"), list) and len(
            subsonic_song.get("isrc")) > 0 else None,
        duration=int(subsonic_song.get("duration", 0)),
        quality=_parse_quality(subsonic_song)
    )


def _parse_playlist(subsonic_playlist: dict, fetch_tracks: bool = True, cover: bytes = None) -> SubsonicPlaylist:
    tracks = []
    if fetch_tracks:
        for entry in subsonic_playlist.get("entry", []):
            track = _parse_track(entry)
            if track:
                tracks.append(track)

    return SubsonicPlaylist(
        id=subsonic_playlist.get("id"),
        name=subsonic_playlist.get("name"),
        tracks=tracks if fetch_tracks else None,
        image=cover
    )


def _parse_quality(subsonic_track: dict) -> TrackQuality:
    try:
        codec = subsonic_track.get('contentType', 'audio/mpeg').split('/')[1].lower()
        bit_depth = subsonic_track.get("bitDepth", 16)
        bit_rate = subsonic_track.get("bitRate", 128)
        sample_rate = subsonic_track.get("samplingRate", 44100)

        if codec in ["mp3", "aac", "opus"]:
            return TrackQuality.LOW
        elif codec == "flac":
            if (bit_depth <= 16 or bit_rate >= 500) and sample_rate >= 44100:  # 16-bit 44.1kHz
                return TrackQuality.LOSSLESS
            if (bit_depth > 16 or bit_rate >= 1500) and sample_rate >= 48000:  # 24-bit 192kHz
                return TrackQuality.HI_RES_LOSSLESS

            return TrackQuality.LOSSLESS  # fallback for flac

    except (IndexError, AttributeError, TypeError):
        pass

    return TrackQuality.UNKNOWN


def _generate_salt(length: int = 10) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def _generate_token(password: str, salt: str) -> str:
    return hashlib.md5((password + salt).encode("utf-8")).hexdigest()


def login_subsonic(server_url: str, username: str, password: str, db: Database) -> (bool, str, dict):
    try:
        subsonic_manager = SubsonicManager(url=server_url, username=username, db=db, password=password)
        resp = subsonic_manager._request("ping")
        if resp.get("status") != "ok":
            return False, f"Failed to authenticate with Subsonic server: {resp.get('error', 'Unknown error')}", {}

        save_subsonic_info_to_db(db, server_url, username, password)

        return True, "Successfully authenticated with Subsonic.", {}
    except Exception as e:
        return False, f"Failed to connect to Subsonic server: {e}", {}


class SubsonicManager(Manager):
    PLATFORM = Platform.SUBSONIC

    def __init__(self, url: str, username: str, db: Database, password: str = None):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password or get_subsonic_login_password(db, self.base_url, username)
        self.api_version = "1.16.1"
        self.client_name = "syncphony"
        self.db = db

    def _request(self, endpoint: str, params: dict = None, count: int = 0) -> dict | bytes:
        salt = _generate_salt()
        token = _generate_token(self.password, salt)

        default_params = {
            "u": self.username,
            "t": token,
            "s": salt,
            "v": self.api_version,
            "c": self.client_name,
            "f": "json"
        }
        all_params = {**default_params, **(params or {})}
        response = requests.get(f"{self.base_url}/rest/{endpoint}.view", params=all_params, timeout=10)

        try:
            response.raise_for_status()
        except requests.Timeout:
            log.error(f"Request to {self.base_url}/rest/{endpoint}.view timed out.")
            return self._request(endpoint, params, count + 1) if count < 3 else {}

        if response.headers.get("Content-Type") == "application/json":
            resp_json = response.json()

            if resp_json.get("subsonic-response", {}).get("status") == "failed":
                log.error(f"Subsonic API error: {resp_json['subsonic-response'].get('error')}")
                return {}

            return resp_json["subsonic-response"]
        elif response.headers.get("Content-Type") == "image/png" or response.headers.get(
                "Content-Type") == "image/jpeg":
            return response.content
        else:
            log.error(f"Unexpected response type: {response.headers.get('Content-Type')}")
            return {}

    def _get_cover_art(self, cover_art: str) -> Optional[bytes]:
        try:
            resp = self._request("getCoverArt", {"id": cover_art, "size": 500, "format": "png"})
            if isinstance(resp, bytes):
                return resp
            else:
                log.error(f"Failed to fetch cover art for ID {cover_art}")
                return None
        except Exception as e:
            log.error(f"Unexpected error fetching cover art for ID {cover_art}: {e}")
            return None

    def is_multi_user(self) -> bool:
        return False

    def get_track(self, track_id: str) -> Optional[SubsonicTrack]:
        try:
            resp = self._request("getSong", {"id": track_id})
            song = resp.get("song")
            if not song:
                return None
            return _parse_track(song)
        except Exception as e:
            log.error(f"Error fetching track {track_id}: {e}")
            return None

    def get_album(self, album_id: str) -> Optional[SubsonicAlbum]:
        try:
            resp = self._request("getAlbum", {"id": album_id})
            album_data = resp.get("album")
            if not album_data:
                return None
            return _parse_album(album_data)
        except Exception as e:
            log.error(f"Error fetching album {album_id}: {e}")
            return None

    def get_artist(self, artist_id: str) -> Optional[SubsonicArtist]:
        try:
            resp = self._request("getArtist", {"id": artist_id})
            artist_data = resp.get("artist")
            if not artist_data:
                return None
            return _parse_artist(artist_data)
        except Exception as e:
            log.error(f"Error fetching artist {artist_id}: {e}")
            return None

    def get_artist_tracks(self, artist_id: str) -> List[SubsonicTrack]:
        try:
            resp = self._request("getArtist", {"id": artist_id})
            artist = _parse_artist(resp.get("artist"))
            albums = resp.get("artist", {}).get("album", [])
            tracks = []
            for album in albums:
                album_obj = _parse_album(album, artist)
                album_detail = self._request("getAlbum", {"id": album["id"]}).get("album")
                for song in album_detail.get("song", []):
                    tracks.append(_parse_track(song, artist, album_obj))
            return tracks
        except Exception as e:
            log.error(f"Error fetching tracks for artist {artist_id}: {e}")
            return []

    def get_playlist(self, playlist_id: str, fetch_tracks: bool = True, fetch_albums: bool = False) -> Optional[
        SubsonicPlaylist]:
        try:
            resp = self._request("getPlaylist", {"id": playlist_id})
            playlist = resp.get("playlist")

            # cover = self._get_cover_art(playlist.get("coverArt"))
            return _parse_playlist(playlist, fetch_tracks, cover=None) if playlist else None
        except Exception as e:
            log.error(f"Error fetching playlist {playlist_id}: {e}")
            return None

    def get_user_playlists(self, user_id: str = None) -> List[SubsonicPlaylist]:
        try:
            resp = self._request("getPlaylists")
            playlists = []
            playlists.extend(
                [_parse_playlist(pl, fetch_tracks=False, cover=None) for pl in
                 # cover=self._get_cover_art(pl.get("coverArt"))
                 resp.get("playlists", {}).get("playlist", [])])
            return playlists
        except Exception as e:
            log.error(f"Error fetching user playlists: {e}")
            return []

    def get_favorite_tracks(self, user_id: str = None) -> Optional[SubsonicFavoriteTracksPlaylist]:
        try:
            resp = self._request("getStarred")
            songs = resp.get("starred", {}).get("song", [])
            tracks = []
            for s in songs:
                tracks.append(_parse_track(s))
            return SubsonicFavoriteTracksPlaylist(name="Starred Tracks", tracks=tracks)
        except Exception as e:
            log.error(f"Error fetching favorite tracks: {e}")
            return None

    def search_tracks_by_query(self, query: str) -> List[SubsonicTrack]:
        try:
            resp = self._request("search3", {"query": query})
            songs = resp.get("searchResult3", {}).get("song", [])
            results = []
            for s in songs:
                results.append(_parse_track(s))
            return results
        except Exception as e:
            log.error(f"Error searching tracks by query '{query}': {e}")
            return []

    def search_tracks_by_isrc(self, isrc: str) -> List[SubsonicTrack]:
        return []  # Subsonic does not support ISRC natively

    def search_albums_by_query(self, query: str) -> List[SubsonicAlbum]:
        try:
            resp = self._request("search3", {"query": query, "songCount": 0, "artistCount": 0})
            albums = []
            for a in resp.get("searchResult3", {}).get("album", []):
                albums.append(_parse_album(a))
            return albums
        except Exception as e:
            log.error(f"Error searching albums by query '{query}': {e}")
            return []

    def search_albums_by_upc(self, upc: str) -> List[SubsonicAlbum]:
        return []  # Subsonic does not support UPC

    def search_artists_by_query(self, query: str) -> List[SubsonicArtist]:
        try:
            resp = self._request("search3", {"query": query})
            return [_parse_artist(a) for a in resp.get("searchResult3", {}).get("artist", [])]
        except Exception as e:
            log.error(f"Error searching artists by query '{query}': {e}")
            return []

    def supports_lyrics(self) -> bool:
        return True

    def get_lyrics(self, track: SubsonicTrack) -> Optional[str]:
        try:
            resp = self._request("getLyricsBySongId", {"id": track.id})
            if len(resp.get('lyricsList', {}).get('structuredLyrics', [])) > 0 and False:
                def format_time(ms):
                    """Convert microseconds to [mm:ss.xx] format"""
                    seconds = ms / 1000
                    t = datetime.timedelta(seconds=seconds)
                    total_minutes = int(t.total_seconds() // 60)
                    seconds_left = t.total_seconds() % 60
                    return f"[{total_minutes:02}:{seconds_left:05.2f}]"

                output = ""
                # Convert and print the output
                for entry in resp.get('lyricsList', {}).get('structuredLyrics', [])[0].get('line', []):
                    timestamp = format_time(entry['start'])
                    output += f"{timestamp} {entry['value']}\n"

                return output
            else:
                resp = self._request("getLyrics", {"artist": track.artist.name, "title": track.name})
                return resp.get("lyrics", {}).get('value', "")
        except Exception as e:
            log.error(f"Error fetching lyrics for track {track.id}: {e}")
            return None

    def create_empty_playlist(self, name: str, description: str = "", cover: bytes = None, user_id: str = None) -> \
            Optional[SubsonicPlaylist]:
        try:
            resp = self._request("createPlaylist", {"name": name})
            if resp.get("status") == "ok":
                pl_id = resp.get("playlist", {}).get("id")
                return SubsonicPlaylist(id=pl_id, name=name, tracks=[])

            return None
        except Exception as e:
            log.error(f"Error creating empty playlist '{name}': {e}")
            return None

    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[SubsonicTrack], user_id: str = None) -> bool:
        try:

            track_ids = tuple([track.id for track in tracks])
            # resp = self._request("updatePlaylist", {
            #     "playlistId": playlist.id,
            #     "songIdToAdd": track_ids
            # })
            # return resp.get("status") == "ok"

            for offset in range(0, len(track_ids), 10):
                batch = track_ids[offset:offset + 100]
                resp = self._request("updatePlaylist", {
                    "playlistId": playlist.id,
                    "songIdToAdd": batch
                })
                if resp.get("status") != "ok":
                    log.error(f"Failed to add tracks {batch} to playlist {playlist.name}: {resp.get('error')}")
                    return False

            return True

        except Exception as e:
            log.error(f"Error adding tracks to playlist '{playlist.name}': {e}")
            return False

    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        try:
            resp = self._request("deletePlaylist", {"id": playlist_id})
            return resp.get("status") == "ok"
        except Exception as e:
            log.error(f"Error removing playlist with ID '{playlist_id}': {e}")
            return False
