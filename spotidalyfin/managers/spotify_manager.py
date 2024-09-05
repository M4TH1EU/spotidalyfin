# spotify_manager.py
import random
import time

import cachebox
import spotipy
from spotipy import SpotifyOAuth

from spotidalyfin.utils.decorators import rate_limit


class SpotifyManager:
    def __init__(self, client_id, client_secret):
        scopes = ['playlist-read-private', 'playlist-read-collaborative', 'user-library-read']
        self.client = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id, client_secret=client_secret,
                                                                redirect_uri="http://127.0.0.1:6969", scope=scopes))

    @cachebox.cached(cachebox.LRUCache(maxsize=128))
    @rate_limit
    def get_playlist_tracks(self, playlist_id):
        tracks = []
        results = self.client.playlist_items(playlist_id, limit=50, additional_types='track')
        tracks.extend(results.get('items'))

        while results.get('next'):
            time.sleep(random.uniform(0.1, 0.3))
            results = self.client.playlist_items(playlist_id, limit=50, offset=len(tracks), additional_types='track')
            tracks.extend(results.get('items'))

        return tracks

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_track(self, track_id):
        return self.client.track(track_id)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_album(self, album_id):
        return self.client.album(album_id)

    @cachebox.cached(cachebox.LRUCache(maxsize=16))
    @rate_limit
    def get_liked_songs(self):
        tracks = []
        results = self.client.current_user_saved_tracks(limit=50)
        tracks.extend(results.get('items'))

        while results.get('next'):
            time.sleep(random.uniform(0.1, 0.3))
            results = self.client.current_user_saved_tracks(limit=50, offset=len(tracks))
            tracks.extend(results.get('items'))

        return tracks
