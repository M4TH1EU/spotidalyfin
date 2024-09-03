# spotify_manager.py
from minim import spotify


class SpotifyManager:
    def __init__(self, client_id, client_secret):
        self.client = spotify.WebAPI(
            client_id=client_id,
            client_secret=client_secret,
            flow="pkce",
            scopes=spotify.WebAPI.get_scopes("all"),
            web_framework=None
        )

    def get_playlist_tracks(self, playlist_id):
        tracks = []
        results = self.client.get_playlist_items(playlist_id, limit=50)
        tracks.extend(results.get('items'))

        while results.get('next'):
            tracks.extend(self.client.get_playlist_items(playlist_id, limit=50, offset=len(tracks)).get('items', []))

        return tracks

    def get_track(self, track_id):
        return self.client.get_track(track_id)

    def get_album(self, album_id):
        return self.client.get_album(album_id)

    def get_liked_songs(self):
        tracks = []
        results = self.client.get_saved_tracks(limit=50)
        tracks.extend(results.get('items'))

        while results.get('next'):
            tracks.extend(self.client.get_saved_tracks(limit=50, offset=len(tracks)).get('items', []))

        return tracks
