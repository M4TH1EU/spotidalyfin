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
from spotidalyfin.models import Track, Album, Artist, TrackQuality
from spotidalyfin.models.base_album import SpotifyAlbum
from spotidalyfin.models.base_artist import SpotifyArtist
from spotidalyfin.models.base_manager import Manager
from spotidalyfin.models.base_playlist import FavoriteTracksPlaylist, Playlist, SpotifyPlaylist
from spotidalyfin.models.base_track import SpotifyTrack


def _parse_track(spotipy_track: dict) -> SpotifyTrack:
    return SpotifyTrack(
        name=spotipy_track['name'],
        id=spotipy_track['id'],
        artist=_parse_artist(spotipy_track["artists"][0]) if spotipy_track.get("artists") else None,
        album=_parse_album(spotipy_track["album"]) if spotipy_track.get("album") else None,
        duration=spotipy_track.get("duration_ms", 0),
        quality=TrackQuality.LOW
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
        artist=Artist(
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
        tracks=[_parse_track(item["track"]) for item in spotipy_playlist.get("tracks", {}).get("items", [])],
        image=spotipy_playlist.get("images", [{}])[0].get("url", "")
    )


def _parse_favorite_tracks(spotipy_playlist: dict) -> FavoriteTracksPlaylist:
    return FavoriteTracksPlaylist(
        id="favorite_tracks",
        name="Liked Songs",
        tracks=[_parse_track(item["track"]) for item in spotipy_playlist.get("items", [])],
        image=spotipy_playlist.get("images", [{"url": ""}])[0].get("url", "")
    )


def create_temp_oauth(client_id: str, client_secret: str) -> SpotifyOAuth:
    """Create a temporary (in-memory storage) SpotifyOAuth object with the given parameters."""
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPES,
        cache_handler=MemoryCacheHandler(),  # don't cache anything
        open_browser=False
    )


def login(oauth: SpotifyOAuth, response_url: str, db: Database = None) -> (bool, str):
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
    def __init__(self, username: str, db: Database):
        self.username = username
        self.db = db

        # Initialize Spotify client(s)
        self.oauth = get_spotify_oauth(db, username)
        self.client = spotipy.Spotify(auth_manager=self.oauth)
        self.anonymous_client = spotipy.Spotify(auth_manager=SpotifyAnon())

    def get_track(self, track_id: str) -> Optional[Track]:
        try:
            spotipy_track = self.client.track(track_id)
            return _parse_track(spotipy_track)

        except SpotifyException as e:
            logging.exception(f"Failed to fetch Spotify track with ID {track_id}")
            return None

    def get_album(self, album_id: str) -> Optional[Album]:
        try:
            spotipy_album = self.client.album(album_id)
            return _parse_album(spotipy_album)

        except SpotifyException as e:
            logging.exception(f"Failed to fetch Spotify album with ID {album_id}")
            return None

    def get_artist(self, artist_id: str) -> Optional[Artist]:
        try:
            spotipy_artist = self.client.artist(artist_id)
            return _parse_artist(spotipy_artist)

        except SpotifyException as e:
            logging.exception(f"Failed to fetch Spotify artist with ID {artist_id}")
            return None

    def get_playlist(self, playlist_id: str, fetch_all_tracks: bool = False, fetch_albums: bool = False) -> Optional[
        Playlist]:
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

        if fetch_all_tracks:
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

    def get_user_playlists(self, user_id: str = None) -> list[Playlist]:
        try:
            playlists = []
            if not user_id:
                playlists = self.client.current_user_playlists()
            else:
                playlists = self.client.user_playlists(user_id)

            return [_parse_playlist(playlist) for playlist in playlists['items']]

        except SpotifyException as e:
            logging.exception(f"Failed to fetch playlists for user {user_id or self.username}")
            return []

    def get_favorite_tracks(self) -> Optional[FavoriteTracksPlaylist]:
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

    def search_tracks_by_query(self, query: str) -> list[Track]:
        pass

    def search_tracks_by_isrc(self, isrc: str) -> list[Track]:
        pass

    def search_albums(self, query: str) -> list[Album]:
        pass

    def search_artists(self, query: str) -> list[Artist]:
        pass

    def supports_lyrics(self) -> bool:
        return False

    def get_lyrics(self, track: Track) -> str:
        pass

    def create_playlist(self, name: str, tracks: List[Track], description: str = "", cover_url: str = "") -> Playlist:
        pass
