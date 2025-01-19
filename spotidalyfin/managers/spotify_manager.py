import logging
import random
import time
from pathlib import Path
from typing import Optional, List

import cachebox
import spotipy
from spotipy import SpotifyOAuth, SpotifyOauthError, MemoryCacheHandler
from spotipy.exceptions import SpotifyException
from spotipy_anon import SpotifyAnon

from spotidalyfin import cfg, SPOTIFY_SCOPES, SPOTIFY_REDIRECT_URI
from spotidalyfin.db.database import Database
from spotidalyfin.db.helpers import get_authenticated_spotify_profiles, \
    save_spotify_into_db, get_spotify_oauth
from spotidalyfin.exceptions import TrackNotFoundException, AlbumNotFoundException, \
    ArtistNotFoundException, SearchException, PlaylistNotFoundException, PlaylistItemsException, UserPlaylistsException
from spotidalyfin.managers import types
from spotidalyfin.managers.types import Track, Album, Artist, Playlist, Platform
from spotidalyfin.utils.decorators import rate_limit


def create_temporary_oauth(client_id: str, client_secret: str) -> SpotifyOAuth:
    """Create a temporary (in-memory storage) SpotifyOAuth object with the given parameters."""
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPES,
        cache_handler=MemoryCacheHandler(),  # don't cache anything
        open_browser=False
    )


def try_to_authenticate_with_spotify(oauth: SpotifyOAuth, redirect_url: str, db: Database = None) -> (bool, str):
    """
    Try to authenticate with Spotify using the given redirect URL.

    :param oauth: the SpotifyOAuth object to use for authentication
    :param redirect_url: the URL to parse the response code from
    :param db: the database to save the authenticated user to (optional)

    :return: a tuple containing a boolean indicating success and a message
    """
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
        self.anonymous_client = spotipy.Spotify(auth_manager=SpotifyAnon())

    # def is_authenticated(self) -> bool:
    #     """Check if the user has already authenticated with Spotify and has a valid token."""
    #     return self.oauth.validate_token(self.oauth.get_cached_token())

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_track(self, track_id: str) -> Track:
        """
        Fetch a single track by its ID.

        :param track_id: the ID of the track to fetch

        :raises TrackNotFoundException: if the track cannot be found
        """
        try:
            spotipy_track = self.client.track(track_id)
            return types.track_from_spotify_track(spotipy_track)
        except SpotifyException as e:
            logging.exception(f"Failed to fetch track with ID {track_id}")
            raise TrackNotFoundException(f"Failed to fetch track with ID {track_id}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_album(self, album_id: str) -> Album:
        """
        Fetch an album by its ID.

        :param album_id: the ID of the album to fetch

        :raises AlbumNotFoundException: if the album cannot be found
        """
        try:
            spotipy_album = self.client.album(album_id)
            return types.album_from_spotify_album(spotipy_album)
        except SpotifyException as e:
            logging.exception(f"Failed to fetch album with ID {album_id}")
            raise AlbumNotFoundException(f"Failed to fetch album with ID {album_id}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_artist(self, artist_id: str) -> Artist:
        """
        Fetch an artist by their ID.

        :param artist_id: the ID of the artist to fetch

        :raises ArtistNotFoundException: if the artist cannot be found
        """
        try:
            spotipy_artist = self.client.artist(artist_id)
            return types.artist_from_spotify_artist(spotipy_artist)
        except SpotifyException as e:
            logging.exception(f"Failed to fetch artist with ID {artist_id}")
            raise ArtistNotFoundException(f"Failed to fetch artist with ID {artist_id}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def search_artist(self, artist_name: str) -> Optional[Artist]:
        """
        Search for an artist by name and return the first match, if any.

        :param artist_name: the name of the artist to search for

        :raises SpotifyException: if the search fails
        """
        try:
            results = self.client.search(q=artist_name, type='artist')
            artists = results.get('artists', {}).get('items', [])
            return types.artist_from_spotify_artist(artists[0]) if artists else None
        except SpotifyException as e:
            logging.exception(f"Failed to search for artist with name {artist_name}")
            raise SearchException(f"Failed to search for artist with name {artist_name}")

    @cachebox.cached(cachebox.LRUCache(maxsize=16))
    @rate_limit
    def get_liked_songs(self) -> Playlist:
        """
        Fetch the user's liked songs as a playlist.
        :raises PlaylistNotFoundException: if the playlist cannot be found or fetched
        """
        tracks: List[Track] = []
        offset = 0
        limit = 50

        try:
            while True:
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
            logging.exception("Failed to fetch liked songs")
            raise PlaylistNotFoundException("Failed to fetch liked songs")

        return Playlist(
            platform=Platform.SPOTIFY,
            name="Liked Songs",
            image="",
            playlist_id="liked-songs",
            tracks=tracks
        )

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    @rate_limit
    def get_playlist(self, playlist_id: str, retrieve_all_tracks: bool = True,
                     retrieve_all_albums_details: bool = False) -> Playlist:
        """
        Fetch a playlist by its ID and optionally retrieve all tracks and album details.

        :param playlist_id: the ID of the playlist to fetch
        :param retrieve_all_tracks: whether to retrieve all tracks in the playlist (otherwise only the first 100 are fetched)
        :param retrieve_all_albums_details: whether to retrieve all additional album details (barcode,...) for each track in the playlist (slower)

        :raises PlaylistNotFoundException: if an error occurs while fetching the playlist
        :raises PlaylistItemsException: if an error occurs while fetching the tracks in the playlist
        :raises AlbumNotFoundException: if an error occurs while fetching the album details for the tracks in the playlist
        """

        if playlist_id == "liked_songs":
            return self.get_liked_songs()

        try:
            playlist = self.client.playlist(playlist_id)
            anonymous = False
        except SpotifyException as e:
            # Due to Spotify API limitations, if the specified playlist is from Spotify we cannot retrieve its details
            # A workaround is to use the anonymous client to fetch the playlist, but this might be patched in the future
            if "404" in str(e):
                playlist = self.anonymous_client.playlist(playlist_id)
                anonymous = True
            else:
                logging.exception(f"Failed to fetch playlist with ID {playlist_id}, even with the anonymous client")
                raise PlaylistNotFoundException(
                    f"Failed to fetch playlist with ID {playlist_id}, even with the anonymous client")

        if retrieve_all_tracks:
            self._fetch_all_playlist_tracks(playlist, playlist_id, anonymous or False)

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

    def _fetch_all_playlist_tracks(self, playlist: dict, playlist_id: str, anonymous: bool = True) -> None:
        """
        Helper method to fetch all tracks in a playlist.

        :param playlist: the playlist json response from Spotify to fetch tracks for
        :param playlist_id: the ID of the playlist to fetch tracks for
        :param anonymous: whether to use the anonymous client to fetch the tracks (useful for bypassing API limitations)

        :raises PlaylistItemsException: if an error occurs while fetching the tracks
        """
        offset = len(playlist['tracks']['items'])

        try:
            while True:
                if not anonymous:
                    results = self.client.playlist_items(
                        playlist_id=playlist_id,
                        limit=100,
                        offset=offset,
                        additional_types='track'
                    )
                else:
                    results = self.anonymous_client.playlist_items(
                        playlist_id=playlist_id,
                        limit=100,
                        offset=offset,
                        additional_types='track'
                    )
                    time.sleep(
                        random.uniform(0.5, 1))  # throttle due to anonymous client potentially being rate-limited

                playlist['tracks']['items'].extend(results['items'])
                if not results.get('next'):
                    break

                offset += 100
        except SpotifyException as e:
            logging.exception(f"Failed to fetch all tracks for playlist with ID {playlist_id}")
            raise PlaylistItemsException(f"Failed to fetch all tracks for playlist with ID {playlist_id}")

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    @rate_limit
    def get_user_playlists(self, user_id: str = "me") -> List[Playlist]:
        """
        Fetch all playlists for the given user.

        :param user_id: the user ID to fetch playlists for, defaults to "me" (the current user)

        :raises UserPlaylistsException: if an error occurs while fetching the playlists
        """
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
            logging.exception(f"Failed to fetch playlists for user with ID {user_id}")
            raise UserPlaylistsException(f"Failed to fetch playlists for user with ID {user_id}")
