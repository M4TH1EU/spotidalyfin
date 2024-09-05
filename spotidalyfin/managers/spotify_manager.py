# spotify_manager.py
import random
import time

from minim import spotify

from spotidalyfin.utils.decorators import rate_limit, cache_2months


class SpotifyManager:
    def __init__(self, client_id, client_secret):
        self.client = spotify.WebAPI(
            client_id=client_id,
            client_secret=client_secret,
            flow="pkce",
            scopes=spotify.WebAPI.get_scopes("all"),
            web_framework=None
        )

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

    @cache_2months
    def get_track(self, track_id):
        return self.client.get_track(track_id)

    @cache_2months
    def get_album(self, album_id):
        return self.client.get_album(album_id)

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
