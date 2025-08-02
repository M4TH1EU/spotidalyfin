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
from spotidalyfin.utils.logger import log


def _parse_cover(jellyfin_item: dict) -> Optional[bytes]:
    cover_tag = jellyfin_item.get("ImageTags", {}).get("Primary") or jellyfin_item.get(
        "PrimaryImageTag") or jellyfin_item.get("AlbumPrimaryImageTag")
    if not cover_tag:
        cover_tag = jellyfin_item.get("PrimaryImageTag")
    if not cover_tag:
        return None

    item_id = jellyfin_item.get("Id") or jellyfin_item.get("AlbumId")
    if cover_tag and item_id:
        return f"{jellyfin_item.get('base_url', '')}/Items/{item_id}/Images/Primary?tag={cover_tag}"  # TODO : fix
    return None


def _parse_artist(jellyfin_artist: dict) -> JellyfinArtist:
    return JellyfinArtist(
        name=jellyfin_artist.get("Name"),
        id=jellyfin_artist.get("Id"),
        # image=_parse_cover(jellyfin_artist),
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
        # cover=_parse_cover(jellyfin_album),
        num_volumes=None,
        tracks=None
    )


def _parse_track(jellyfin_track: dict) -> JellyfinTrack:
    artist = _parse_artist(jellyfin_track["ArtistItems"][0])
    album = _parse_album(jellyfin_track)

    # Extract duration from RunTimeTicks (100-nanosecond units)
    duration_ticks = jellyfin_track.get("RunTimeTicks", 0)

    return JellyfinTrack(
        name=jellyfin_track["Name"],
        id=jellyfin_track["Id"],
        artist=artist,
        album=album,
        isrc=None,
        duration=int(duration_ticks / 10_000_000) if duration_ticks else None,
        quality=_parse_quality(jellyfin_track),
    )


def _parse_quality(jellyfin_track: dict) -> TrackQuality:
    try:
        media_streams = jellyfin_track.get("MediaSources", [])[0].get("MediaStreams", [])
        audio_stream = next((s for s in media_streams if s.get("Type") == "Audio"), None)
        if not audio_stream:
            return TrackQuality.UNKNOWN

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

    return TrackQuality.UNKNOWN


def _parse_playlist(jellyfin_playlist: dict) -> JellyfinPlaylist:
    items = jellyfin_playlist.get("Items", [])

    return JellyfinPlaylist(
        id=jellyfin_playlist.get("Id"),
        name=jellyfin_playlist.get("Name"),
        tracks=[_parse_track(item) for item in items],
        # image=_parse_cover(jellyfin_playlist)
    )


def login_jellyfin(server_url: str, api_key: str, db: Database) -> (bool, str, dict):
    """
    Try to authenticate with Jellyfin server using the provided URL and API key.
    Returns a tuple of (success: bool, message: str).
    """
    try:
        jellyfin_manager = JellyfinManager(url=server_url, db=db, api_key=api_key)
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

    def _request(self, path, params=None, method="GET", headers=None, data=None, count: int = 0) -> Optional[
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
            response = requests.get(url, params=params, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, params=params, headers=headers, timeout=10, data=data)
        elif method == "DELETE":
            response = requests.delete(url, params=params, headers=headers, timeout=10)

        try:
            response.raise_for_status()
        except requests.Timeout:
            log.error(f"Request to Jellyfin API timed out after {count} attempts. Retrying...")
            return self._request(path, params, method, headers, data, count + 1) if count < 3 else []

        if response.status_code == 204:  # No Content
            return response.ok

        try:
            resp_json = response.json()
            if 'Items' in resp_json and resp_json.get('TotalRecordCount', 0) >= 0:
                for item in resp_json['Items']:
                    item['base_url'] = self.url
                return resp_json['Items']
            elif 'Lyrics' in resp_json:
                return resp_json.get('Lyrics', [])
            elif isinstance(resp_json, list):
                return resp_json
            elif 'Id' in resp_json:
                return resp_json
            else:
                log.warning(f"Unexpected response format: {resp_json}")
                return []
        except ValueError:
            log.exception("Failed to parse JSON response from Jellyfin API.")
        except requests.exceptions.RequestException as e:
            log.exception(f"Request to Jellyfin API failed: {e}")

        return []

    def _modify_image(self, item_id: str, data: bytes, type="Primary") -> bool:
        try:
            self._request(f"Items/{item_id}/Images/{type}", method="POST", headers={'Content-Type': "image/jpeg"},
                          data=data)
            return True
        except Exception as e:
            log.error(f"Failed to modify image for item {item_id}: {e}")
            return False

    def is_multi_user(self) -> bool:
        return True

    def get_users(self) -> List[Tuple[str, str]]:
        try:
            users = self._request("Users")
            return [(str(user.get("Id")), str(user.get("Name"))) for user in users]
        except Exception as e:
            log.error(f"Failed to retrieve users from Jellyfin: {e}")
            return []

    def _get_default_admin_user_id(self) -> Optional[str]:
        """This method retrieves the first user with admin privileges to use in some API calls due to Jellyfin's API limitations."""
        try:
            users = self._request("Users")
            for user in users:
                if user.get("Policy", {}).get("IsAdministrator", False):
                    return user.get("Id")

            log.warning("No admin user found in Jellyfin. Some features may not work.")
            return None
        except Exception as e:
            log.error(f"Failed to retrieve admin user from Jellyfin: {e}")
            return None

    def get_track(self, track_id: str) -> Optional[JellyfinTrack]:
        try:
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
        except Exception as e:
            log.error(f"Failed to retrieve track {track_id} from Jellyfin: {e}")
            return None

    def get_album(self, album_id: str) -> Optional[JellyfinAlbum]:
        try:
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
        except Exception as e:
            log.error(f"Failed to retrieve album {album_id} from Jellyfin: {e}")
            return None

    def get_artist(self, artist_id: str) -> Optional[JellyfinArtist]:
        try:
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
        except Exception as e:
            log.error(f"Failed to retrieve artist {artist_id} from Jellyfin: {e}")
            return None

    def get_artist_tracks(self, artist_id: str) -> list[JellyfinTrack]:
        try:
            path = "Items"
            params = {
                "recursive": "true",
                "limit": 50,
                "fields": "MediaSources",
                "includeItemTypes": "Audio",
                "artistIds": artist_id
            }
            results = self._request(path, params)
            return [_parse_track(item) for item in results]
        except Exception as e:
            log.error(f"Failed to retrieve tracks for artist {artist_id} from Jellyfin: {e}")
            return []

    def get_playlist(self, playlist_id: str, fetch_tracks: bool = True, fetch_albums: bool = False) -> Optional[
        JellyfinPlaylist]:
        try:
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
        except Exception as e:
            log.error(f"Failed to retrieve playlist {playlist_id} from Jellyfin: {e}")
            return None

    def get_user_playlists(self, user_id: str = None) -> list[JellyfinPlaylist]:
        try:
            if user_id is None:
                log.warning("No user ID provided, returning empty playlist list.")
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
        except Exception as e:
            log.error(f"Failed to retrieve playlists for user {user_id} from Jellyfin: {e}")
            return []

    def get_favorite_tracks(self, user_id: str = None) -> Optional[JellyfinFavoriteTracksPlaylist]:
        try:
            if user_id is None:
                log.warning("No user ID provided, returning no favorites list.")
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

            return JellyfinFavoriteTracksPlaylist(
                name="Favorite Tracks",
                tracks=[_parse_track(item) for item in jellyfin_favorites],
            )
        except Exception as e:
            log.error(f"Failed to retrieve favorite tracks for user {user_id} from Jellyfin: {e}")
            return None

    def search_tracks_by_query(self, query: str) -> list[JellyfinTrack]:
        try:
            path = "Items"
            params = {
                "searchTerm": query,
                "recursive": "true",
                "limit": 25,
                "fields": "MediaSources",
                "includeItemTypes": "Audio"
            }
            results = self._request(path, params)
            return [_parse_track(item) for item in results]
        except Exception as e:
            log.error(f"Failed to search tracks by query '{query}' in Jellyfin: {e}")
            return []

    def search_tracks_by_isrc(self, isrc: str) -> list[JellyfinTrack]:
        log.warning("Jellyfin does not support searching by ISRC. Returning empty list.")
        return []

    def search_albums_by_query(self, query: str) -> list[JellyfinAlbum]:
        try:
            path = "Items"
            params = {
                "searchTerm": query,
                "includeItemTypes": "MusicAlbum",
                "recursive": "true",
                "limit": 15
            }
            results = self._request(path, params)
            return [_parse_album(item) for item in results]
        except Exception as e:
            log.error(f"Failed to search albums by query '{query}' in Jellyfin: {e}")
            return []

    def search_albums_by_upc(self, upc: str) -> list[JellyfinAlbum]:
        log.warning("Jellyfin does not support searching by UPC. Returning empty list.")
        return []

    def search_artists_by_query(self, query: str) -> list[JellyfinArtist]:
        try:
            path = "Items"
            params = {
                "searchTerm": query,
                "includeItemTypes": "MusicArtist",
                "recursive": "true",
                "limit": 15
            }
            results = self._request(path, params)
            return [_parse_artist(item) for item in results]
        except Exception as e:
            log.error(f"Failed to search artists by query '{query}' in Jellyfin: {e}")
            return []

    def supports_lyrics(self) -> bool:
        return True

    def get_lyrics(self, track: Track) -> Optional[str]:
        try:
            path = f"Audio/{track.id}/Lyrics"
            results = self._request(path)
            if not results:
                return None

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
        except Exception as e:
            log.error(f"Failed to retrieve lyrics for track {track.name} by {track.artist.name} from Jellyfin: {e}")
            return None

    def create_empty_playlist(self, name: str, description: str = "", cover: bytes = None, user_id: str = None) -> \
            Optional[
                JellyfinPlaylist]:
        try:
            if not user_id:
                log.error("No user ID provided, cannot create playlist.")

            path = f"Playlists"
            params = {
                "name": name,
                "userId": user_id,
                "mediaType": "Audio",
            }

            result = self._request(path, params, method="POST")
            if not result or "Id" not in result:
                log.error("Failed to create playlist.")
                return None

            if cover:
                self._modify_image(result.get('Id'), cover)

            return self.get_playlist(result.get("Id"), fetch_tracks=False, fetch_albums=False)
        except Exception as e:
            log.error(f"Failed to create empty playlist '{name}': {e}")
            return None

    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[JellyfinTrack], user_id: str = None) -> bool:
        try:
            path = f"Playlists/{playlist.id}/Items"

            for offset in range(0, len(tracks), 10):
                batch_tracks = tracks[offset:offset + 10]
                if not batch_tracks:
                    continue
                params = {
                    "ids": ",".join(track.id for track in batch_tracks),
                    "userId": user_id,  # Jellyfin requires a user ID for adding items to playlists
                }
                result = self._request(path, params, method="POST")
                if not result:
                    log.error(f"Failed to add tracks to playlist {playlist.name}.")
                    return False

            # params = {
            #     "ids": ",".join(track.id for track in tracks),
            #     "userId": user_id,
            # }
            # result = self._request(path, params, method="POST")
            # if not result:
            #     log.error(f"Failed to add tracks to playlist {playlist.name}.")
            #     return False

            return True
        except Exception as e:
            log.error(f"Failed to add tracks to playlist {playlist.name}: {e}")
            return False

        # https://jellyfin.broillet.ch/Playlists/0a992713243ba5a49d5b974feb099eb0/Items?ids=d86fcae36930181015551268fdd19c4d&userId=5180b2a096734d748dec001c3a0d2bb6

    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        try:
            path = f"Items/{playlist_id}"
            result = self._request(path, method="DELETE")
            if not result:
                return False

            return True
        except Exception as e:
            log.error(f"Failed to remove playlist {playlist_id}: {e}")
            return False
