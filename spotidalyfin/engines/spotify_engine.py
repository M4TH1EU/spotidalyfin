import logging
import random
import time
from typing import Optional, List

import spotipy
from spotipy import SpotifyOAuth, MemoryCacheHandler
from spotipy.exceptions import SpotifyException, SpotifyOauthError
from spotipy_anon import SpotifyAnon

from spotidalyfin import SPOTIFY_REDIRECT_URI, SPOTIFY_SCOPES
from spotidalyfin.db.database import Database
from spotidalyfin.db.helpers import get_spotify_oauth, get_authenticated_spotify_profiles, save_spotify_into_db
from spotidalyfin.models import Track, TrackQuality
from spotidalyfin.models.album import SpotifyAlbum
from spotidalyfin.models.artist import SpotifyArtist
from spotidalyfin.models.enums import Platform
from spotidalyfin.models.manager import Manager
from spotidalyfin.models.playlist import SpotifyPlaylist, \
    SpotifyFavoriteTracksPlaylist, Playlist
from spotidalyfin.models.track import SpotifyTrack


def _parse_track(spotipy_track: dict) -> SpotifyTrack:
    return SpotifyTrack(
        name=spotipy_track['name'],
        id=spotipy_track['id'],
        artist=_parse_artist(spotipy_track["artists"][0]) if spotipy_track.get("artists") else None,
        album=_parse_album(spotipy_track["album"]) if spotipy_track.get("album") else None,
        duration=spotipy_track.get("duration_ms", 0),
        quality=TrackQuality.LOW,
        isrc=spotipy_track.get("external_ids", {}).get("isrc", "").upper()
    )


def _parse_artist(spotipy_artist: dict) -> SpotifyArtist:
    return SpotifyArtist(
        name=spotipy_artist["name"],
        id=spotipy_artist["id"],
        genres=spotipy_artist.get("genres", []),
        image=spotipy_artist.get("images", [{}])[0].get("url", ""),
    )


def _parse_album(spotipy_album: dict) -> SpotifyAlbum:
    return SpotifyAlbum(
        name=spotipy_album["name"],
        id=spotipy_album["id"],
        artist=SpotifyArtist(
            name=spotipy_album["artists"][0]["name"],
            id=spotipy_album["artists"][0]["id"]
        ),
        barcode=spotipy_album.get('external_ids', {}).get('upc', ''),
        release_date=spotipy_album.get("release_date", None),
        cover_url=spotipy_album.get('images', [{}])[0].get('url', ''),
        num_volumes=None,
        tracks=None
    )


def _parse_playlist(spotipy_playlist: dict) -> SpotifyPlaylist:
    return SpotifyPlaylist(
        id=spotipy_playlist['id'],
        name=spotipy_playlist['name'],
        description=spotipy_playlist.get('description', ''),
        tracks=[_parse_track(item["track"]) for item in spotipy_playlist.get("tracks", {}).get("items", [])],
        image=spotipy_playlist.get("images", [{}])[0].get("url", "") if spotipy_playlist['images'] else ""
    )


def _parse_favorite_tracks(spotipy_playlist: dict) -> SpotifyFavoriteTracksPlaylist:
    return SpotifyFavoriteTracksPlaylist(
        name="Liked Songs",
        tracks=[_parse_track(item["track"]) for item in spotipy_playlist.get("items", [])],
        image=spotipy_playlist.get("images", [{"url": ""}])[0].get("url", "")
    )


def create_temp_oauth_spotify(client_id: str, client_secret: str) -> SpotifyOAuth:
    """Create a temporary (in-memory storage) SpotifyOAuth object with the given parameters."""
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPES,
        cache_handler=MemoryCacheHandler(),  # don't cache anything
        open_browser=False
    )


def login_spotify(oauth: SpotifyOAuth, response_url: str, db: Database = None) -> (bool, str):
    try:
        code = oauth.parse_response_code(response_url)
        if code:
            oauth.get_access_token(code, check_cache=False)

            if db:
                username = spotipy.Spotify(auth_manager=oauth).current_user()["id"]
                if username in get_authenticated_spotify_profiles(db):
                    return False, "This account is already authenticated, please remove it and try again."

                save_spotify_into_db(db, username, oauth)

            return True, "Login successful"
    except SpotifyOauthError as e:
        if hasattr(e, "error_description"):
            return False, f"Failed to authenticate with Spotify: {e.error_description}"

    return False, "Failed to authenticate with Spotify. Please try again."


class SpotifyManager(Manager):
    PLATFORM = Platform.SPOTIFY

    def __init__(self, username: str, db: Database):
        self.username = username
        self.db = db

        # Initialize Spotify client(s)
        self.oauth = get_spotify_oauth(db, username)
        self.client = spotipy.Spotify(auth_manager=self.oauth)
        self.anonymous_client = spotipy.Spotify(auth_manager=SpotifyAnon())

    def get_track(self, track_id: str) -> Optional[SpotifyTrack]:
        try:
            spotipy_track = self.client.track(track_id)
            return _parse_track(spotipy_track)

        except SpotifyException as e:
            logging.exception(f"Failed to fetch Spotify track with ID {track_id}")
            return None

    def get_album(self, album_id: str) -> Optional[SpotifyAlbum]:
        try:
            spotipy_album = self.client.album(album_id)
            return _parse_album(spotipy_album)

        except SpotifyException as e:
            logging.exception(f"Failed to fetch Spotify album with ID {album_id}")
            return None

    def get_artist(self, artist_id: str) -> Optional[SpotifyArtist]:
        try:
            spotipy_artist = self.client.artist(artist_id)
            return _parse_artist(spotipy_artist)

        except SpotifyException as e:
            logging.exception(f"Failed to fetch Spotify artist with ID {artist_id}")
            return None

    def get_playlist(self, playlist_id: str, fetch_tracks: bool = False, fetch_albums: bool = False) -> Optional[
        SpotifyPlaylist]:
        if playlist_id == "favorite_tracks":
            return self.get_favorite_tracks()

        used_anonymous_client = False
        playlist = None
        try:
            playlist = self.client.playlist(playlist_id)
        except SpotifyException as e:
            if "404" in str(e):
                try:
                    # Due to Spotify API limitations, if the specified playlist is from Spotify we cannot retrieve its details
                    # A workaround is to use the anonymous client to fetch the playlist, but this might be patched in the future
                    playlist = self.anonymous_client.playlist(playlist_id)
                    used_anonymous_client = True
                except Exception as e:
                    logging.exception(f"Failed to fetch playlist with ID {playlist_id} using anonymous client")
                    return None
            else:
                logging.exception(f"Failed to fetch playlist with ID {playlist_id}, even with the anonymous client")
                return None

        if fetch_tracks:
            total = playlist["tracks"]["total"]
            tracks = playlist["tracks"]["items"]

            for offset in range(0, total, 50):
                try:
                    current_client = self.anonymous_client if used_anonymous_client else self.client
                    results = current_client.playlist_items(playlist_id, offset=offset, limit=50,
                                                            additional_types="track")
                except SpotifyException as e:
                    logging.exception(
                        f"Failed to fetch playlist items for playlist ID {playlist_id} at offset {offset}")
                    return None

                if used_anonymous_client:  # TODO: check if needed
                    time.sleep(random.uniform(0.3, 0.7))

                tracks.extend(results["items"])

        if fetch_albums:
            for item in playlist['tracks']['items']:
                track = item['track']
                album_id = track['album']['id']
                track['album'] = self.client.album(album_id)

        return _parse_playlist(playlist)

    def get_user_playlists(self, user_id: str = None) -> list[SpotifyPlaylist]:
        try:
            if not user_id:
                playlists = self.client.current_user_playlists()
            else:
                playlists = self.client.user_playlists(user_id)

            return [_parse_playlist(playlist) for playlist in playlists['items']]

        except SpotifyException as e:
            logging.exception(f"Failed to fetch playlists for user {user_id or self.username}")
            return []

    def get_favorite_tracks(self) -> Optional[SpotifyFavoriteTracksPlaylist]:
        try:
            liked_songs = self.client.current_user_saved_tracks(limit=50, offset=0)
            total = liked_songs['total']
            tracks = liked_songs['items']

            for offset in range(0, total, 50):
                liked_songs = self.client.current_user_saved_tracks(limit=50, offset=offset)
                if not liked_songs['items']:
                    break

                for item in liked_songs['items']:
                    track = item['track']
                    tracks.append(track)

            liked_songs['items'] = tracks

            return _parse_favorite_tracks(liked_songs)

        except SpotifyException as e:
            logging.exception("Failed to fetch favorite tracks")
            return None

    def search_tracks_by_query(self, query: str) -> list[SpotifyTrack]:
        try:
            results = self.client.search(q=query, type='track', limit=10)
            return [_parse_track(item) for item in results['tracks']['items']]

        except SpotifyException as e:
            logging.exception(f"Failed to search tracks with query '{query}'")
            return []

    def search_tracks_by_isrc(self, isrc: str) -> list[SpotifyTrack]:
        try:
            results = self.client.search(q=f"isrc:{isrc}", type='track', limit=10)
            return [_parse_track(item) for item in results['tracks']['items']]

        except SpotifyException as e:
            logging.exception(f"Failed to search tracks with ISRC '{isrc}'")
            return []

    def search_albums_by_query(self, query: str) -> list[SpotifyAlbum]:
        try:
            results = self.client.search(q=query, type='album', limit=10)
            return [_parse_album(item) for item in results['albums']['items']]

        except SpotifyException as e:
            logging.exception(f"Failed to search albums with query '{query}'")
            return []

    def search_albums_by_upc(self, upc: str) -> list[SpotifyAlbum]:
        try:
            results = self.client.search(q=f"upc:{upc}", type='album', limit=10)
            return [_parse_album(item) for item in results['albums']['items']]

        except SpotifyException as e:
            logging.exception(f"Failed to search albums with UPC '{upc}'")
            return []

    def search_artists(self, query: str) -> list[SpotifyArtist]:
        try:
            results = self.client.search(q=query, type='artist', limit=10)
            return [_parse_artist(item) for item in results['artists']['items']]

        except SpotifyException as e:
            logging.exception(f"Failed to search artists with query '{query}'")
            return []

    def supports_lyrics(self) -> bool:
        return False

    def get_lyrics(self, track: Track) -> str:
        pass

    def create_empty_playlist(self, name: str, description: str = "", cover_url: str = "") -> Optional[SpotifyPlaylist]:
        try:
            playlist = self.client.user_playlist_create(
                user=self.username,
                name=name,
                public=False,
                description=description
            )

            if cover_url:
                self.client.playlist_upload_cover_image(playlist['id'], cover_url)

            return _parse_playlist(playlist)
        except Exception as e:
            logging.exception(f"Failed to create TIDAL playlist '{name}': {e}")
            return None

    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[SpotifyTrack]) -> bool:
        try:
            track_ids = [track.id for track in tracks if track.id]
            if not track_ids:
                return False

            self.client.playlist_add_items(playlist.id, track_ids)
            return True
        except SpotifyException as e:
            logging.exception(f"Failed to add tracks to playlist {playlist.id}: {e}")
            return False

    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        try:
            self.client.current_user_unfollow_playlist(playlist_id=playlist_id)
            return True
        except SpotifyException as e:
            logging.exception(f"Failed to remove playlist with ID {playlist_id}: {e}")
            return False
