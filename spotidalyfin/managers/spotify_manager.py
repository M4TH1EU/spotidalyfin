# spotify_manager.py

import random
import time
from pathlib import Path
from typing import Optional

import cachebox
import spotipy
from spotipy import SpotifyOAuth, CacheFileHandler

from spotidalyfin import cfg
from spotidalyfin.managers import types
from spotidalyfin.managers.types import Track, Album, Artist, Playlist, Platform
from spotidalyfin.utils.decorators import rate_limit


class SpotifyManager:
    """Manages interactions with the Spotify API, including fetching tracks, albums, artists, playlists, and liked songs."""

    def __init__(self, client_id: str, client_secret: str):
        """Initializes the SpotifyManager with API credentials and sets up the Spotipy client."""
        scopes = ['playlist-read-private', 'playlist-read-collaborative', 'user-library-read']
        token_file = Path(cfg.get("config-dir")) / ".spotipy-token"
        token_file.parent.mkdir(parents=True, exist_ok=True)

        self.client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri="http://127.0.0.1:6969",
                scope=scopes,
                cache_handler=CacheFileHandler(str(token_file)),
                open_browser=False
            )
        )

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_track(self, track_id: str) -> Track:
        """Fetches a single track by its ID."""
        try:
            spotipy_track = self.client.track(track_id)
            return types.track_from_spotify_track(spotipy_track)
        except spotipy.SpotifyException as e:
            raise ValueError(f"Failed to fetch track with ID {track_id}: {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_album(self, album_id: str) -> Album:
        """Fetches an album by its ID."""
        try:
            spotipy_album = self.client.album(album_id)
            return types.album_from_spotify_album(spotipy_album)
        except spotipy.SpotifyException as e:
            raise ValueError(f"Failed to fetch album with ID {album_id}: {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_artist(self, artist_id: str) -> Artist:
        """Fetches an artist by their ID."""
        try:
            spotipy_artist = self.client.artist(artist_id)
            return types.artist_from_spotify_artist(spotipy_artist)
        except spotipy.SpotifyException as e:
            raise ValueError(f"Failed to fetch artist with ID {artist_id}: {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def search_artist(self, artist_name: str) -> Optional[Artist]:
        """Searches for an artist by name and returns the first match, if any."""
        try:
            results = self.client.search(q=artist_name, type='artist')
            artists = results.get('artists', {}).get('items', [])
            if artists:
                return types.artist_from_spotify_artist(artists[0])
            return None
        except spotipy.SpotifyException as e:
            raise ValueError(f"Failed to search for artist '{artist_name}': {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=16))
    @rate_limit
    def get_liked_songs(self) -> Playlist:
        """Fetches the user's liked songs as a playlist."""
        tracks: list[Track] = []
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
                time.sleep(random.uniform(0.1, 0.3))
            except spotipy.SpotifyException as e:
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
        """Fetches a playlist by its ID and optionally retrieve its tracks and eventually the album details (retrieve_tracks must be True)."""
        try:
            spotipy_playlist = self.client.playlist(playlist_id)  # already loads the first 100 tracks

            if retrieve_all_tracks:
                while True:
                    try:
                        results = self.client.playlist_items(
                            playlist_id=playlist_id,
                            limit=100,
                            offset=len(spotipy_playlist['tracks']['items']),
                            additional_types='track'
                        )

                        spotipy_playlist['tracks']['items'].extend(results['items'])

                        if not results.get('next'):
                            break

                        # time.sleep(random.uniform(0.1, 0.3))
                    except spotipy.SpotifyException as e:
                        raise ValueError(f"Failed to fetch tracks for playlist {playlist_id}: {e}")

            if retrieve_all_albums_details:
                for _ in range(len(spotipy_playlist['tracks']['items'])):
                    album = self.client.album(spotipy_playlist['tracks']['items'][_]['track']['album']['id'])
                    spotipy_playlist['tracks']['items'][_]['track']['album'] = album

            return Playlist(
                platform=Platform.SPOTIFY,
                name=spotipy_playlist['name'],
                image=spotipy_playlist['images'][0]['url'] if spotipy_playlist.get('images') else "",
                playlist_id=playlist_id,
                tracks=[
                    types.track_from_spotify_track(item['track'])
                    for item in spotipy_playlist['tracks']['items']
                    if item.get('track')
                ]
            )
        except spotipy.SpotifyException as e:
            raise ValueError(f"Failed to fetch playlist with ID {playlist_id}: {e}")

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    @rate_limit
    def get_user_playlists(self, user_id: str = "me") -> list[Playlist]:
        """Fetches all playlists for the given user."""
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
        except spotipy.SpotifyException as e:
            raise ValueError(f"Failed to fetch playlists for user '{user_id}': {e}")
