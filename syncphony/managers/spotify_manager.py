import random
import time
from typing import Optional, List

import spotipy
from spotipy import SpotifyOAuth, MemoryCacheHandler, CacheHandler
from spotipy.exceptions import SpotifyException
from spotipy_anon import SpotifyAnon
from sqlmodel import Session, select

from syncphony.constants import SPOTIFY_SCOPES, SPOTIFY_REDIRECT_URI
from syncphony.db.models import SpotifyAccount
from syncphony.types import Track, TrackQuality
from syncphony.types.album import SpotifyAlbum
from syncphony.types.artist import SpotifyArtist
from syncphony.types.enums import Platform
from syncphony.types.manager import Manager
from syncphony.types.playlist import SpotifyPlaylist, \
    SpotifyFavoriteTracksPlaylist, Playlist
from syncphony.types.track import SpotifyTrack
from syncphony.types.utils import get_as_base64
from syncphony.utils.logger import log


class SpotipyCacheDatabaseHandler(CacheHandler):
    """
    Handles reading and writing cached Spotify authorization tokens
    in the Syncphony database.
    """

    def __init__(self, db_session: Session, client_id: str, client_secret: str, username: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.db_session = db_session

    def get_cached_token(self) -> dict:
        token_info = self.db_session.exec(
            select(SpotifyAccount).where(SpotifyAccount.username == self.username)).first()

        if token_info:
            return {
                "access_token": token_info.access_token,
                "token_type": "Bearer",
                # "expires_in": 0,
                "expires_at": token_info.expires_at,
                "refresh_token": token_info.refresh_token,
                "scope": " ".join(SPOTIFY_SCOPES)
            }

        return {}

    def save_token_to_cache(self, token_info) -> None:
        token_info_rec = self.db_session.exec(
            select(SpotifyAccount).where(SpotifyAccount.username == self.username)).first()
        token_info_rec.access_token = token_info["access_token"]
        token_info_rec.expires_at = token_info["expires_at"]
        token_info_rec.refresh_token = token_info.get("refresh_token", "")
        self.db_session.add(token_info_rec)
        self.db_session.commit()


def _get_image(spotipy_object: dict) -> Optional[bytes]:
    """Get the first image URL from a Spotipy object and convert it to base64."""
    if 'images' in spotipy_object and spotipy_object['images']:
        return get_as_base64(spotipy_object['images'][0].get('url', ''))
    return None


def _parse_track(spotipy_track: dict) -> SpotifyTrack:
    return SpotifyTrack(
        name=spotipy_track['name'],
        id=spotipy_track['id'],
        artist=_parse_artist(spotipy_track["artists"][0]) if spotipy_track.get("artists") else None,
        album=_parse_album(spotipy_track["album"]) if spotipy_track.get("album") else None,
        duration=int(spotipy_track.get("duration_ms", 0) / 1000),
        quality=TrackQuality.LOW,
        isrc=spotipy_track.get("external_ids", {}).get("isrc", "").upper()
    )


def _parse_artist(spotipy_artist: dict) -> SpotifyArtist:
    return SpotifyArtist(
        name=spotipy_artist["name"],
        id=spotipy_artist["id"],
        genres=spotipy_artist.get("genres", []),
        # image=_get_image(spotipy_artist)
    )


def _parse_album(spotipy_album: dict) -> SpotifyAlbum:
    if not len(spotipy_album.get('artists')) > 0:  # TODO: investigate why this happens
        log.error(f"Album {spotipy_album.get('name', 'Unknown')} has no artists, skipping.")

    return SpotifyAlbum(
        name=spotipy_album["name"],
        id=spotipy_album["id"],
        artist=_parse_artist(spotipy_album["artists"][0]) if spotipy_album.get("artists") else None,
        barcode=spotipy_album.get('external_ids', {}).get('upc', ''),
        release_date=spotipy_album.get("release_date", None),
        # cover=_get_image(spotipy_album),
        num_volumes=None,
        tracks=None
    )


def _parse_playlist(spotipy_playlist: dict) -> SpotifyPlaylist:
    return SpotifyPlaylist(
        id=spotipy_playlist['id'],
        name=spotipy_playlist['name'],
        description=spotipy_playlist.get('description', ''),
        tracks=[_parse_track(item["track"]) for item in spotipy_playlist.get("tracks", {}).get("items", [])],
        # image=_get_image(spotipy_playlist)
    )


def _parse_favorite_tracks(spotipy_playlist: dict) -> SpotifyFavoriteTracksPlaylist:
    return SpotifyFavoriteTracksPlaylist(
        name="Liked Songs",
        tracks=[_parse_track(item["track"]) for item in spotipy_playlist.get("items", [])],
        # image=_get_image(spotipy_playlist)
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


class SpotifyManager(Manager):
    PLATFORM = Platform.SPOTIFY

    def __init__(self, username: str, db_session: Session):
        self.username = username
        self.db_session = db_session

        # Initialize Spotify client(s)
        account = db_session.exec(
            select(SpotifyAccount).where(SpotifyAccount.username == username)
        ).first()
        if not account:
            raise ValueError(f"No Spotify account found for username {username}")

        oauth = SpotifyOAuth(
            client_id=account.client_id,
            client_secret=account.client_secret,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=SPOTIFY_SCOPES,
            cache_handler=SpotipyCacheDatabaseHandler(db_session, account.client_id, account.client_secret, username),
            open_browser=False
        )
        self.client = spotipy.Spotify(auth_manager=oauth)
        self.anonymous_client = spotipy.Spotify(auth_manager=SpotifyAnon())

    def is_multi_user(self) -> bool:
        return False

    def get_track(self, track_id: str) -> Optional[SpotifyTrack]:
        try:
            spotipy_track = self.client.track(track_id)
            return _parse_track(spotipy_track)

        except SpotifyException as e:
            log.exception(f"Failed to fetch Spotify track with ID {track_id}")
            return None

    def get_album(self, album_id: str) -> Optional[SpotifyAlbum]:
        try:
            spotipy_album = self.client.album(album_id)
            return _parse_album(spotipy_album)

        except SpotifyException as e:
            log.exception(f"Failed to fetch Spotify album with ID {album_id}")
            return None

    def get_artist(self, artist_id: str) -> Optional[SpotifyArtist]:
        try:
            spotipy_artist = self.client.artist(artist_id)
            return _parse_artist(spotipy_artist)

        except SpotifyException as e:
            log.exception(f"Failed to fetch Spotify artist with ID {artist_id}")
            return None

    def get_artist_tracks(self, artist_id: str) -> list[SpotifyTrack]:
        try:
            results = self.client.artist_top_tracks(artist_id)  # TODO: retrieve all tracks instead of just top tracks
            return [_parse_track(track) for track in results['tracks']]

        except SpotifyException as e:
            log.exception(f"Failed to fetch top tracks for artist with ID {artist_id}")
            return []

    def get_playlist(self, playlist_id: str, fetch_tracks: bool = True, fetch_albums: bool = False) -> Optional[
        SpotifyPlaylist]:
        if playlist_id == "favorite_tracks":
            return self.get_favorite_tracks()

        if "https://open.spotify.com/playlist/" in playlist_id:
            # Extract the playlist ID from the URL
            playlist_id = playlist_id.split("/")[-1].split("?")[0]

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
                    log.exception(f"Failed to fetch playlist with ID {playlist_id} using anonymous client")
                    return None
            else:
                log.exception(f"Failed to fetch playlist with ID {playlist_id}, even with the anonymous client")
                return None

        if fetch_tracks:
            total = playlist["tracks"]["total"]
            tracks = playlist["tracks"]["items"]

            for offset in range(100, total, 100):  # start, total, step size
                try:
                    current_client = self.anonymous_client if used_anonymous_client else self.client
                    results = current_client.playlist_items(playlist_id, offset=offset, limit=100,
                                                            additional_types="track")
                except SpotifyException as e:
                    log.exception(
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
                total = playlists['total']
                for offset in range(0, total, 50):
                    playlists = self.client.current_user_playlists(limit=50, offset=offset)
                    if not playlists['items']:
                        break
            else:
                playlists = self.client.user_playlists(user_id)
                total = playlists['total']
                for offset in range(0, total, 50):
                    playlists = self.client.user_playlists(user_id, limit=50, offset=offset)
                    if not playlists['items']:
                        break

            return [_parse_playlist(playlist) for playlist in playlists['items']]

        except SpotifyException as e:
            log.exception(f"Failed to fetch playlists for user {user_id or self.username}")
            return []

    def get_favorite_tracks(self, user_id: str = None) -> Optional[SpotifyFavoriteTracksPlaylist]:
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
            log.exception("Failed to fetch favorite tracks")
            return None

    def search_tracks_by_query(self, query: str) -> list[SpotifyTrack]:
        try:
            results = self.client.search(q=query, type='track', limit=10)
            return [_parse_track(item) for item in results['tracks']['items']]

        except SpotifyException as e:
            log.exception(f"Failed to search tracks with query '{query}'")
            return []

    def search_tracks_by_isrc(self, isrc: str) -> list[SpotifyTrack]:
        try:
            results = self.client.search(q=f"isrc:{isrc}", type='track', limit=10)
            return [_parse_track(item) for item in results['tracks']['items']]

        except SpotifyException as e:
            log.exception(f"Failed to search tracks with ISRC '{isrc}'")
            return []

    def search_albums_by_query(self, query: str) -> list[SpotifyAlbum]:
        try:
            results = self.client.search(q=query, type='album', limit=10)
            return [_parse_album(item) for item in results['albums']['items']]

        except SpotifyException as e:
            log.exception(f"Failed to search albums with query '{query}'")
            return []

    def search_albums_by_upc(self, upc: str) -> list[SpotifyAlbum]:
        try:
            results = self.client.search(q=f"upc:{upc}", type='album', limit=10)
            return [_parse_album(item) for item in results['albums']['items']]

        except SpotifyException as e:
            log.exception(f"Failed to search albums with UPC '{upc}'")
            return []

    def search_artists_by_query(self, query: str) -> list[SpotifyArtist]:
        try:
            results = self.client.search(q=query, type='artist', limit=10)
            return [_parse_artist(item) for item in results['artists']['items']]

        except SpotifyException as e:
            log.exception(f"Failed to search artists with query '{query}'")
            return []

    def supports_lyrics(self) -> bool:
        return False

    def get_lyrics(self, track: Track) -> Optional[str]:
        pass

    def create_empty_playlist(self, name: str, description: str = "", cover: bytes = None, user_id: str = None) -> \
            Optional[SpotifyPlaylist]:
        try:
            playlist = self.client.user_playlist_create(
                user=self.username,
                name=name,
                public=False,
                description=description
            )

            if cover:
                self.client.playlist_upload_cover_image(playlist['id'], cover)

            return _parse_playlist(playlist)
        except Exception as e:
            log.exception(f"Failed to create TIDAL playlist '{name}': {e}")
            return None

    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[SpotifyTrack], user_id: str = None) -> bool:
        try:
            track_ids = [track.id for track in tracks if track.id]
            if not track_ids:
                return False

            self.client.playlist_add_items(playlist.id, track_ids)
            return True
        except SpotifyException as e:
            log.exception(f"Failed to add tracks to playlist {playlist.id}: {e}")
            return False

    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        try:
            self.client.current_user_unfollow_playlist(playlist_id=playlist_id)
            return True
        except SpotifyException as e:
            log.exception(f"Failed to remove playlist with ID {playlist_id}: {e}")
            return False

    def supports_downloading(self) -> bool:
        return False
