from pathlib import Path
from pathlib import Path
from typing import Optional, List

import cachebox
import spotipy
from spotipy import SpotifyOAuth, SpotifyOauthError, MemoryCacheHandler
from spotipy.exceptions import SpotifyException

from spotidalyfin import cfg, SPOTIFY_SCOPES, SPOTIFY_REDIRECT_URI
from spotidalyfin.db.database import Database
from spotidalyfin.db.helpers import get_authenticated_spotify_profiles, \
    save_spotify_into_db, get_spotify_oauth
from spotidalyfin.managers import types
from spotidalyfin.managers.types import Track, Album, Artist, Playlist, Platform
from spotidalyfin.utils.decorators import rate_limit


def create_temporary_oauth(client_id: str, client_secret: str) -> SpotifyOAuth:
    """Create a SpotifyOAuth object with the given parameters."""
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPES,
        cache_handler=MemoryCacheHandler(),  # don't cache anything
        open_browser=False
    )


def try_to_authenticate_with_spotify(oauth: SpotifyOAuth, redirect_url: str, db: Database = None) -> (bool, str):
    """Try to authenticate with Spotify using the given redirect URL."""
    try:
        code = oauth.parse_response_code(redirect_url)
        if code:
            oauth.get_access_token(code, check_cache=False)

            if db:
                username = spotipy.Spotify(auth_manager=oauth).current_user()["id"]
                if username in get_authenticated_spotify_profiles(db):
                    return False, "This account is already authenticated, please remove it and try again."

                save_spotify_into_db(db, username, oauth)
            return True, ""
    except SpotifyOauthError as e:
        if hasattr(e, "error_description"):
            return False, f"Failed to authenticate with Spotify: {e.error_description}"

    return False, "Failed to authenticate with Spotify. Please try again."


class SpotifyManager:
    """Manages interactions with the Spotify API, including tracks, albums, artists, playlists, and liked songs."""

    def __init__(self, username: str, db: Database):
        """Initialize the SpotifyManager with API credentials."""
        token_file = Path(cfg.get("config-dir")) / ".spotipy-token"
        token_file.parent.mkdir(parents=True, exist_ok=True)

        self.oauth = get_spotify_oauth(db, username)
        self.client = spotipy.Spotify(auth_manager=self.oauth)

    # def is_authenticated(self) -> bool:
    #     """Check if the user has already authenticated with Spotify and has a valid token."""
    #     return self.oauth.validate_token(self.oauth.get_cached_token())

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_track(self, track_id: str) -> Track:
        """Fetch a single track by its ID."""
        try:
            spotipy_track = self.client.track(track_id)
            return types.track_from_spotify_track(spotipy_track)
        except SpotifyException as e:
            raise ValueError(f"Failed to fetch track with ID {track_id}: {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_album(self, album_id: str) -> Album:
        """Fetch an album by its ID."""
        try:
            spotipy_album = self.client.album(album_id)
            return types.album_from_spotify_album(spotipy_album)
        except SpotifyException as e:
            raise ValueError(f"Failed to fetch album with ID {album_id}: {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_artist(self, artist_id: str) -> Artist:
        """Fetch an artist by their ID."""
        try:
            spotipy_artist = self.client.artist(artist_id)
            return types.artist_from_spotify_artist(spotipy_artist)
        except SpotifyException as e:
            raise ValueError(f"Failed to fetch artist with ID {artist_id}: {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def search_artist(self, artist_name: str) -> Optional[Artist]:
        """Search for an artist by name and return the first match, if any."""
        try:
            results = self.client.search(q=artist_name, type='artist')
            artists = results.get('artists', {}).get('items', [])
            return types.artist_from_spotify_artist(artists[0]) if artists else None
        except SpotifyException as e:
            raise ValueError(f"Failed to search for artist '{artist_name}': {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=16))
    @rate_limit
    def get_liked_songs(self) -> Playlist:
        """Fetch the user's liked songs as a playlist."""
        tracks: List[Track] = []
        offset = 0
        limit = 50

        while True:
            try:
                results = self.client.current_user_saved_tracks(limit=limit, offset=offset)
                items = results.get('items', [])

                tracks.extend(
                    types.track_from_spotify_track(item['track'])
                    for item in items
                    if item.get('track')
                )

                if not results.get('next'):
                    break

                offset += limit
            except SpotifyException as e:
                raise ValueError(f"Failed to fetch liked songs: {e}")

        return Playlist(
            platform=Platform.SPOTIFY,
            name="Liked Songs",
            image="",
            playlist_id="liked-songs",
            tracks=tracks
        )

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    @rate_limit
    def get_playlist(self, playlist_id: str, retrieve_all_tracks: bool = False,
                     retrieve_all_albums_details: bool = False) -> Playlist:
        """Fetch a playlist by its ID and optionally retrieve all tracks and album details."""
        try:
            playlist = self.client.playlist(playlist_id)

            if retrieve_all_tracks:
                self._fetch_all_playlist_tracks(playlist, playlist_id)

            if retrieve_all_albums_details:
                for item in playlist['tracks']['items']:
                    track = item['track']
                    album_id = track['album']['id']
                    track['album'] = self.client.album(album_id)

            return Playlist(
                platform=Platform.SPOTIFY,
                name=playlist['name'],
                image=playlist['images'][0]['url'] if playlist.get('images') else "",
                playlist_id=playlist_id,
                tracks=[
                    types.track_from_spotify_track(item['track'])
                    for item in playlist['tracks']['items']
                    if item.get('track')
                ]
            )
        except SpotifyException as e:
            raise ValueError(f"Failed to fetch playlist with ID {playlist_id}: {e}")

    def _fetch_all_playlist_tracks(self, playlist: dict, playlist_id: str) -> None:
        """Helper method to fetch all tracks in a playlist."""
        offset = len(playlist['tracks']['items'])

        while True:
            try:
                results = self.client.playlist_items(
                    playlist_id=playlist_id,
                    limit=100,
                    offset=offset,
                    additional_types='track'
                )

                playlist['tracks']['items'].extend(results['items'])
                if not results.get('next'):
                    break

                offset += 100
            except SpotifyException as e:
                raise ValueError(f"Failed to fetch additional tracks for playlist {playlist_id}: {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    @rate_limit
    def get_user_playlists(self, user_id: str = "me") -> List[Playlist]:
        """Fetch all playlists for the given user."""
        try:
            playlists_data = self.client.current_user_playlists() if user_id == "me" else self.client.user_playlists(
                user_id)

            items = playlists_data.get('items', [])

            return [
                Playlist(
                    platform=Platform.SPOTIFY,
                    name=item['name'],
                    image=item['images'][0]['url'] if item.get('images') else "",
                    playlist_id=item['id'],
                    tracks=[]
                )
                for item in items
            ]
        except SpotifyException as e:
            raise ValueError(f"Failed to fetch playlists for user '{user_id}': {e}")
