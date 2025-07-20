import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

import requests

from spotidalyfin.db.database import Database
from spotidalyfin.db.helpers import save_jellyfin_info_to_db, get_jellyfin_api_key
from spotidalyfin.models import Track, TrackQuality
from spotidalyfin.models.album import JellyfinAlbum
from spotidalyfin.models.artist import JellyfinArtist
from spotidalyfin.models.enums import Platform
from spotidalyfin.models.manager import Manager
from spotidalyfin.models.playlist import JellyfinPlaylist, \
    JellyfinFavoriteTracksPlaylist, Playlist
from spotidalyfin.models.track import JellyfinTrack
from spotidalyfin.models.utils import get_as_base64


def _parse_cover_url(jellyfin_item: dict) -> Optional[str]:
    cover_tag = jellyfin_item.get("ImageTags", {}).get("Primary") or jellyfin_item.get(
        "PrimaryImageTag") or jellyfin_item.get("AlbumPrimaryImageTag")
    if not cover_tag:
        cover_tag = jellyfin_item.get("PrimaryImageTag")
    if not cover_tag:
        return None

    item_id = jellyfin_item.get("Id") or jellyfin_item.get("AlbumId")
    if cover_tag and item_id:
        return f"/Items/{item_id}/Images/Primary?tag={cover_tag}"
    return None


def _parse_artist(jellyfin_artist: dict) -> JellyfinArtist:
    return JellyfinArtist(
        name=jellyfin_artist.get("Name"),
        id=jellyfin_artist.get("Id"),
        image=_parse_cover_url(jellyfin_artist),
    )


def _parse_album(jellyfin_album: dict) -> JellyfinAlbum:
    artist = _parse_artist(jellyfin_album["AlbumArtists"][0])
    album_name = jellyfin_album.get("Album") or jellyfin_album.get("Name")  # from track | from album
    album_id = jellyfin_album.get("AlbumId") or jellyfin_album.get("Id")  # from track | from album

    release_date_str = jellyfin_album.get("PremiereDate")
    release_date = datetime.fromisoformat(release_date_str.replace("Z", "+00:00")) if release_date_str else None

    return JellyfinAlbum(
        name=album_name,
        id=album_id,
        artist=artist,
        barcode="",
        release_date=release_date,
        cover_url=_parse_cover_url(jellyfin_album),
        num_volumes=None,
        tracks=None
    )


def _parse_track(jellyfin_track: dict) -> JellyfinTrack:
    artist = _parse_artist(jellyfin_track["ArtistItems"][0])
    album = _parse_album(jellyfin_track)

    # Extract duration from RunTimeTicks (100-nanosecond units)
    duration_ticks = jellyfin_track.get("RunTimeTicks", 0)
    duration_ms = int(duration_ticks / 10_000_000) if duration_ticks else None

    return JellyfinTrack(
        name=jellyfin_track["Name"],
        id=jellyfin_track["Id"],
        artist=artist,
        album=album,
        isrc=None,
        duration=duration_ms,
        quality=_parse_quality(jellyfin_track),
    )


def _parse_quality(jellyfin_track: dict) -> TrackQuality:
    try:
        media_streams = jellyfin_track.get("MediaSources", [])[0].get("MediaStreams", [])
        audio_stream = next((s for s in media_streams if s.get("Type") == "Audio"), None)
        if not audio_stream:
            return None

        codec = audio_stream.get("Codec", "").lower()
        bit_depth = audio_stream.get("BitDepth", 0)
        sample_rate = audio_stream.get("SampleRate", 0)

        if codec in ["mp3", "aac", "opus"]:
            return TrackQuality.LOW
        if codec == "flac":
            if bit_depth == 16 and sample_rate == 44100:
                return TrackQuality.LOSSLESS
            if bit_depth == 24 and sample_rate >= 48000:
                return TrackQuality.HI_RES_LOSSLESS
            return TrackQuality.LOSSLESS  # fallback for flac

    except (IndexError, AttributeError, TypeError):
        pass

    return None


def _parse_playlist(jellyfin_playlist: dict) -> JellyfinPlaylist:
    items = jellyfin_playlist.get("Items", [])

    return JellyfinPlaylist(
        id=jellyfin_playlist.get("Id"),
        name=jellyfin_playlist.get("Name"),
        tracks=[_parse_track(item) for item in items],
        image=_parse_cover_url(jellyfin_playlist)
    )


def _parse_favorite_tracks(jellyfin_playlist: list) -> JellyfinFavoriteTracksPlaylist:
    return JellyfinFavoriteTracksPlaylist(
        name="Favorite Tracks",
        tracks=[_parse_track(item) for item in jellyfin_playlist],
    )


def login_jellyfin(server_url: str, api_key: str, db: Database) -> (bool, str, dict):
    """
    Try to authenticate with Jellyfin server using the provided URL and API key.
    Returns a tuple of (success: bool, message: str).
    """
    jellyfin_manager = JellyfinManager(url=server_url, db=db, api_key=api_key)
    try:
        users = jellyfin_manager.get_users()
        if not users:
            return False, "No users found on the Jellyfin server. Please check your API key and server URL.", {}

        save_jellyfin_info_to_db(db, server_url, jellyfin_manager.api_key)

        return True, "Successfully authenticated with Jellyfin.", {}
    except requests.exceptions.RequestException as e:
        return False, f"Failed to connect to Jellyfin server: {e}", {}


class JellyfinManager(Manager):
    PLATFORM = Platform.JELLYFIN

    def __init__(self, url, db: Database, api_key: str = None):
        self.url = url.rstrip("/")
        self.api_key = get_jellyfin_api_key(db, url) if api_key is None else api_key
        self.db = db

        self.default_admin_user_id = self._get_default_admin_user_id()

    def _request(self, path, params=None, method="GET", headers=None, data=None, timeout: int = 30) -> Optional[
        list | dict | bool]:
        """
        Perform a GET request to the Jellyfin API.
        Returns the JSON response as a dictionary.
        """
        if params is None:
            params = {}
        if headers is None:
            headers = {}

        url = f"{self.url}/{path.lstrip('/')}"
        headers.update({"X-Emby-Token": self.api_key})

        response = None
        if method == "GET":
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, params=params, headers=headers, timeout=timeout, data=data)
        elif method == "DELETE":
            response = requests.delete(url, params=params, headers=headers, timeout=timeout)

        response.raise_for_status()

        if response.status_code == 204:  # No Content
            return response.ok

        try:
            resp_json = response.json()
            if 'Items' in resp_json and resp_json.get('TotalRecordCount', 0) >= 0:
                return resp_json['Items']
            elif 'Lyrics' in resp_json:
                return resp_json.get('Lyrics', [])
            elif isinstance(resp_json, list):
                return resp_json
            elif 'Id' in resp_json:
                return resp_json
            else:
                logging.warning(f"Unexpected response format: {resp_json}")
                return []
        except ValueError:
            logging.exception("Failed to parse JSON response from Jellyfin API.")
        except requests.exceptions.RequestException as e:
            logging.exception(f"Request to Jellyfin API failed: {e}")

        return []

    def _modify_image(self, item_id: str, data: bytes, type="Primary"):
        self._request(f"Items/{item_id}/Images/{type}", method="POST", headers={'Content-Type': "image/jpeg"},
                      data=data)

    def is_multi_user(self) -> bool:
        return True

    def get_users(self) -> List[Tuple[str, str]]:
        users = self._request("Users")
        return [(str(user.get("Id")), str(user.get("Name"))) for user in users]

    def _get_default_admin_user_id(self) -> Optional[str]:
        """This method retrieves the first user with admin privileges to use in some API calls due to Jellyfin's API limitations."""
        users = self._request("Users")
        for user in users:
            if user.get("Policy", {}).get("IsAdministrator", False):
                return str(user.get("Id"))

        logging.warning("No admin user found in Jellyfin server.")
        return None

    def get_track(self, track_id: str) -> Optional[JellyfinTrack]:
        path = f"Items"
        params = {
            "ids": track_id,
            "mediaTypes": "Audio",
            "fields": "MediaSources",
            "includeItemTypes": "Audio"
        }
        result = self._request(path, params)
        if not result:
            return None
        jellyfin_track = result[0]
        return _parse_track(jellyfin_track)

    def get_album(self, album_id: str) -> Optional[JellyfinAlbum]:
        path = f"Items"
        params = {
            "ids": album_id,
            "includeItemTypes": "MusicAlbum"
        }
        result = self._request(path, params)
        if not result:
            return None
        jellyfin_album = result[0]
        return _parse_album(jellyfin_album)

    def get_artist(self, artist_id: str) -> Optional[JellyfinArtist]:
        path = f"Items"
        params = {
            "ids": artist_id,
            "includeItemTypes": "MusicArtist",
        }
        result = self._request(path, params)
        if not result:
            return None
        jellyfin_artist = result[0]
        return _parse_artist(jellyfin_artist)

    def get_playlist(self, playlist_id: str, fetch_tracks: bool = True, fetch_albums: bool = False) -> Optional[
        JellyfinPlaylist]:
        path = f"Items"
        params = {
            "ids": playlist_id,
            "includeItemTypes": "Playlist",
        }
        result = self._request(path, params)
        if not result:
            return None
        jellyfin_playlist = result[0]

        if fetch_tracks:
            # path = f"Playlists/{playlist_id}/Items" # broken without browser session
            path = f"Users/{self.default_admin_user_id}/Items"
            params = {
                "parentId": playlist_id,
                "mediaTypes": "Audio",
            }
            items = self._request(path, params)
            if not items:
                items = []
            jellyfin_playlist["Items"] = items

        if fetch_albums:
            # album data should already be included with the fetch_tracks call
            pass

        return _parse_playlist(jellyfin_playlist)

    def get_user_playlists(self, user_id: str = None) -> list[JellyfinPlaylist]:
        if user_id is None:
            logging.warning("No user ID provided, returning empty playlist list.")
            return []

        path = f"Users/{user_id}/Items"
        params = {
            "includeItemTypes": "Playlist",
            "recursive": "true",
        }
        result = self._request(path, params)
        if not result:
            return []

        return [_parse_playlist(item) for item in result]

    def get_favorite_tracks(self, user_id: str = None) -> Optional[JellyfinFavoriteTracksPlaylist]:
        if user_id is None:
            logging.warning("No user ID provided, returning no favorites list.")
            return None

        path = f"Users/{user_id}/Items"
        params = {
            "Filters": "IsFavorite",
            "Recursive": "true",
            "IncludeItemTypes": "Audio",
        }
        jellyfin_favorites = self._request(path, params)
        if not jellyfin_favorites:
            return None

        return _parse_favorite_tracks(jellyfin_favorites)

    def search_tracks_by_query(self, query: str) -> list[JellyfinTrack]:
        path = "Items"
        params = {
            "searchTerm": query,
            "recursive": "true",
            "limit": 10,
            "fields": "MediaSources",
            "includeItemTypes": "Audio"
        }
        results = self._request(path, params)
        return [_parse_track(item) for item in results]

    def search_tracks_by_isrc(self, isrc: str) -> list[JellyfinTrack]:
        logging.warning("Jellyfin does not support searching by ISRC. Returning empty list.")
        return []

    def search_albums_by_query(self, query: str) -> list[JellyfinAlbum]:
        path = "Items"
        params = {
            "searchTerm": query,
            "includeItemTypes": "MusicAlbum",
            "recursive": "true",
            "limit": 10
        }
        results = self._request(path, params)
        return [_parse_album(item) for item in results]

    def search_albums_by_upc(self, upc: str) -> list[JellyfinAlbum]:
        logging.warning("Jellyfin does not support searching by UPC. Returning empty list.")
        return []

    def search_artists_by_query(self, query: str) -> list[JellyfinArtist]:
        path = "Items"
        params = {
            "searchTerm": query,
            "includeItemTypes": "MusicArtist",
            "recursive": "true",
            "limit": 10
        }
        results = self._request(path, params)
        return [_parse_artist(item) for item in results]

    def supports_lyrics(self) -> bool:
        return True

    def get_lyrics(self, track: Track) -> str:
        path = f"Audio/{track.id}/Lyrics"
        results = self._request(path)
        if not results:
            return ""

        def format_time(ms):
            """Convert microseconds to [mm:ss.xx] format"""
            seconds = ms / 10_000_000
            t = timedelta(seconds=seconds)
            total_minutes = int(t.total_seconds() // 60)
            seconds_left = t.total_seconds() % 60
            return f"[{total_minutes:02}:{seconds_left:05.2f}]"

        output = ""
        # Convert and print the output
        for entry in results:
            timestamp = format_time(entry['Start'])
            output += f"{timestamp} {entry['Text']}\n"

        return output.strip()

    def create_empty_playlist(self, name: str, description: str = "", cover_url: str = "", user_id: str = None) -> \
            Optional[
                JellyfinPlaylist]:
        if not user_id:
            logging.error("No user ID provided, cannot create playlist.")

        path = f"Playlists"
        params = {
            "name": name,
            "userId": user_id,
            "mediaType": "Audio",
        }

        result = self._request(path, params, method="POST")
        if not result or "Id" not in result:
            logging.error("Failed to create playlist.")
            return None

        if cover_url:
            cover_bytes = get_as_base64(cover_url)
            self._modify_image(result.get('Id'), cover_bytes)

        return self.get_playlist(result.get("Id"), fetch_tracks=False, fetch_albums=False)

    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[JellyfinTrack]) -> bool:
        path = f"Playlists/{playlist.id}/Items"
        params = {
            "ids": ",".join(track.id for track in tracks),
            "userId": "6dbbbaa045e34cc597554eb59891d110"
        }
        result = self._request(path, params, method="POST")
        if not result:
            logging.error(f"Failed to add tracks to playlist {playlist.name}.")
            return False

        return True

    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        path = f"Items/{playlist_id}"
        result = self._request(path, method="DELETE")
        if not result:
            return False

        return True
