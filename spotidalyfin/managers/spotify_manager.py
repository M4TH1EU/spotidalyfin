# spotify_manager.py
import random
import time

import cachebox
import spotipy
from spotipy import SpotifyOAuth, CacheFileHandler

from spotidalyfin import cfg
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

    @cachebox.cached(cachebox.LRUCache(maxsize=128))
    @rate_limit
    def get_playlist_tracks(self, playlist_id: str):
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

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_artist(self, artist_id):
        return self.client.artist(artist_id)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def search_artist(self, artist_name):
        artist = self.client.search(q=artist_name, type='artist')
        if artist['artists']['items']:
            return artist['artists']['items'][0]

        return None

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

    @cachebox.cached(cachebox.LRUCache(maxsize=2))
    @rate_limit
    def get_all_playlists_tracks(self):
        playlists = self.client.current_user_playlists()
        all_tracks = []
        for playlist in playlists['items']:
            tracks = self.get_playlist_tracks(playlist['id'])
            all_tracks.extend(tracks)
        return all_tracks

    def get_playlist_name(self, playlist_id):
        return self.get_playlist(playlist_id)['name']

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    @rate_limit
    def get_playlist(self, playlist_id):
        return self.client.playlist(playlist_id)

    def get_playlist_with_tracks(self, playlist_id):
        playlist = self.get_playlist(playlist_id)
        tracks = self.get_playlist_tracks(playlist_id)
        playlist['tracks'] = tracks
        return playlist

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    @rate_limit
    def get_user_playlists(self, user_id):
        playlists = self.client.user_playlists(user_id)
        if 'items' not in playlists:
            return []

        return playlists['items']
