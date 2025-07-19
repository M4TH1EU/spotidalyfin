import logging
from datetime import datetime
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
    pass


def _parse_favorite_tracks(jellyfin_playlist: dict) -> JellyfinFavoriteTracksPlaylist:
    pass


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

    def _get(self, path, params=None, timeout: int = 30) -> list:
        """
        Perform a GET request to the Jellyfin API.
        Returns the JSON response as a dictionary.
        """
        if params is None:
            params = {}

        url = f"{self.url}/{path.lstrip('/')}"
        headers = {"X-Emby-Token": self.api_key}

        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()  # Raise an error for bad responses

        try:
            resp_json = response.json()
            if 'Items' in resp_json and resp_json.get('TotalRecordCount', 0) > 0:
                return resp_json['Items']
            elif isinstance(resp_json, list):
                return resp_json
            else:
                logging.warning(f"Unexpected response format: {resp_json}")
                return []

        except ValueError:
            logging.exception("Failed to parse JSON response fromJellyfin API.")
        return []

    # def _request(self, path, method="GET", params=None, timeout: int = 30) -> dict:
    #     if params is None:
    #         params = {}
    #
    #     url = f"{self.url}/{path.lstrip('/')}"
    #     headers = {"X-Emby-Token": self.api_key}
    #
    #     # Fixes an issue with Jellyfin API where searching with apostrophes doesn't work
    #     if "searchTerm" in params:
    #         params["searchTerm"] = re.sub(r"['\"’‘”“].*", '', params["searchTerm"])
    #
    #     try:
    #         if method == "GET":
    #             response = requests.get(url, headers=headers, params=params)
    #         # elif method == "POST":
    #         #     if image_data:
    #         #         response = requests.post(url, headers=headers, json=json, params=params, data=image_data)
    #         #     else:
    #         #         response = requests.post(url, headers=headers, json=json, params=params)
    #         # elif method == "DELETE":
    #         #     response = requests.delete(url, headers=headers)
    #         # elif method == "DOWNLOAD_GET":
    #         #     return requests.get(url, headers=headers, stream=True, timeout=timeout)
    #         else:
    #             raise ValueError(f"Invalid method: {method}")
    #
    #         response.raise_for_status()
    #         respjson = response.json()
    #         return respjson
    #     except requests.exceptions.RequestException:
    #         return {}

    # def _delete_item(self, item_id):
    #     self._request(f"Items/{item_id}", method="DELETE")
    #
    # def _change_primary_image(self, item_id, image_data):
    #     self._request(f"Items/{item_id}/Images/Primary", method="POST", image_data=image_data)

    def is_multi_user(self) -> bool:
        return True

    def get_users(self) -> List[Tuple[str, str]]:
        users = self._get("Users")
        return [(str(user.get("Id")), str(user.get("Name"))) for user in users]

    def get_track(self, track_id: str) -> Optional[JellyfinTrack]:
        path = f"Items"
        params = {
            "ids": track_id,
            "mediaTypes": "Audio",
            "fields": "MediaSources"
        }
        result = self._get(path, params)
        if not result:
            return None
        jellyfin_track = result[0]
        return _parse_track(jellyfin_track)

    def get_album(self, album_id: str) -> Optional[JellyfinAlbum]:
        path = f"Items"
        params = {
            "ids": album_id,
            "mediaTypes": "MusicAlbum"
        }
        result = self._get(path, params)
        if not result:
            return None
        jellyfin_album = result[0]
        return _parse_album(jellyfin_album)

    def get_artist(self, artist_id: str) -> Optional[JellyfinArtist]:
        path = f"Items"
        params = {
            "ids": artist_id,
            "mediaTypes": "MusicArtist",
        }
        result = self._get(path, params)
        if not result:
            return None
        jellyfin_artist = result[0]
        return _parse_artist(jellyfin_artist)

    def get_playlist(self, playlist_id: str, fetch_tracks: bool = False, fetch_albums: bool = False) -> Optional[
        JellyfinPlaylist]:
        pass

    def get_user_playlists(self, user_id: str = None) -> list[JellyfinPlaylist]:
        pass

    def get_favorite_tracks(self) -> Optional[JellyfinFavoriteTracksPlaylist]:
        pass

    def search_tracks_by_query(self, query: str) -> list[JellyfinTrack]:
        pass

    def search_tracks_by_isrc(self, isrc: str) -> list[JellyfinTrack]:
        pass

    def search_albums_by_query(self, query: str) -> list[JellyfinAlbum]:
        pass

    def search_albums_by_upc(self, upc: str) -> list[JellyfinAlbum]:
        pass

    def search_artists(self, query: str) -> list[JellyfinArtist]:
        pass

    def supports_lyrics(self) -> bool:
        pass

    def get_lyrics(self, track: Track) -> str:
        pass

    def create_empty_playlist(self, name: str, description: str = "", cover_url: str = "") -> Optional[
        JellyfinPlaylist]:
        pass

    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[JellyfinTrack]) -> bool:
        pass

    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        pass
