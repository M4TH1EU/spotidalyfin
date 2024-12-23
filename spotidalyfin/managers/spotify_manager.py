# spotify_manager.py
import random
import time

import cachebox
import spotipy
from spotipy import SpotifyOAuth, CacheFileHandler

from spotidalyfin import cfg
from spotidalyfin.managers import track
from spotidalyfin.managers.track import Track, Album, Artist, Playlist
from spotidalyfin.utils.decorators import rate_limit


class SpotifyManager:
    def __init__(self, client_id, client_secret):
        scopes = ['playlist-read-private', 'playlist-read-collaborative', 'user-library-read']
        token_file = cfg.get("config-dir") / ".spotipy-token"
        token_file.parent.mkdir(parents=True, exist_ok=True)

        self.client = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id, client_secret=client_secret,
                                                                redirect_uri="http://127.0.0.1:6969",
                                                                scope=scopes,
                                                                cache_handler=CacheFileHandler(token_file),
                                                                open_browser=False))

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_track(self, track_id) -> Track:
        spotipy_track = self.client.track(track_id)
        return track.track_from_spotify_track(spotipy_track)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_album(self, album_id) -> Album:
        spotipy_album = self.client.album(album_id)
        return track.album_from_spotify_album(spotipy_album)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_artist(self, artist_id) -> Artist:
        spotipy_artist = self.client.artist(artist_id)
        return track.artist_from_spotify_artist(spotipy_artist)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def search_artist(self, artist_name) -> Artist | None:
        artist = self.client.search(q=artist_name, type='artist')
        if artist['artists']['items']:
            return track.artist_from_spotify_artist(artist['artists']['items'][0])

        return None

    @cachebox.cached(cachebox.LRUCache(maxsize=16))
    @rate_limit
    def get_liked_songs(self) -> Playlist:
        tracks: list[Track] = []
        offset = 0
        limit = 50

        while True:
            # Fetch playlist items
            results = self.client.current_user_saved_tracks(
                limit=limit,
                offset=offset
            )

            # Extract and transform tracks
            tracks.extend(
                track.track_from_spotify_track(item['track'])
                for item in results.get('items', [])
                if item.get('track')
            )

            # Check if there's a next page
            if not results.get('next'):
                break

            offset += limit
            time.sleep(random.uniform(0.1, 0.3))

        playlist = Playlist(
            name="Liked Songs",
            image="",
            playlist_id="liked-songs",
            tracks=tracks
        )

        return playlist

    @cachebox.cached(cachebox.LRUCache(maxsize=128))
    @rate_limit
    def load_playlist_tracks(self, playlist: Playlist | str) -> list[Track]:
        tracks = []
        offset = 0
        limit = 50

        while True:
            # Fetch playlist items
            results = self.client.playlist_items(
                playlist_id=playlist if isinstance(playlist, str) else playlist.playlist_id,
                limit=limit,
                offset=offset,
                additional_types='track'
            )

            # Extract and transform tracks
            tracks.extend(
                track.track_from_spotify_track(item['track'])
                for item in results.get('items', [])
                if item.get('track')
            )

            # Check if there's a next page
            if not results.get('next'):
                break

            offset += limit
            time.sleep(random.uniform(0.1, 0.3))

        return tracks

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    @rate_limit
    def get_playlist(self, playlist_id, load_tracks: bool = False) -> Playlist:
        spotipy_playlist = self.client.playlist(playlist_id)
        return Playlist(
            name=spotipy_playlist['name'],
            image=spotipy_playlist['images'][0]['url'] if spotipy_playlist['images'] else "",
            playlist_id=playlist_id,
            tracks=[] if not load_tracks else self.load_playlist_tracks(playlist_id)
        )

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    @rate_limit
    def get_user_playlists(self, user_id: str) -> list[Playlist]:
        # Fetch playlists based on user ID
        playlists = (self.client.current_user_playlists() if user_id == 'me' else self.client.user_playlists(user_id))

        # Return an empty list if no 'items' key exists
        items = playlists.get('items', [])
        if not items:
            return []

        # Construct the list of Playlist objects
        return [
            Playlist(
                name=item['name'],
                image=item['images'][0]['url'] if item.get('images') else "",
                playlist_id=item['id'],
                tracks=[None] * item['tracks']['total']
            )
            for item in items
        ]
