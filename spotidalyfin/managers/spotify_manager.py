# spotify_manager.py
import random
import time

import cachebox
from minim import spotify

from spotidalyfin.utils.decorators import rate_limit


class SpotifyManager:
    def __init__(self, client_id, client_secret):
        self.client = spotify.WebAPI(
            client_id=client_id,
            client_secret=client_secret,
            flow="pkce",
            scopes=spotify.WebAPI.get_scopes("all"),
            web_framework=None
        )

    @cachebox.cached(cachebox.LRUCache(maxsize=128))
    @rate_limit
    def get_playlist_tracks(self, playlist_id):
        tracks = []
        results = self.client.get_playlist_items(playlist_id, limit=50)
        tracks.extend(results.get('items'))

        while results.get('next'):
            time.sleep(random.uniform(0.1, 0.3))
            results = self.client.get_playlist_items(playlist_id, limit=50, offset=len(tracks))
            tracks.extend(results.get('items'))

        return tracks

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_track(self, track_id):
        return self.client.get_track(track_id)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_album(self, album_id):
        return self.client.get_album(album_id)

    @cachebox.cached(cachebox.LRUCache(maxsize=16))
    @rate_limit
    def get_liked_songs(self):
        tracks = []
        results = self.client.get_saved_tracks(limit=50)
        tracks.extend(results.get('items'))

        while results.get('next'):
            time.sleep(random.uniform(0.1, 0.3))
            results = self.client.get_saved_tracks(limit=50, offset=len(tracks))
            tracks.extend(results.get('items'))

        return tracks
