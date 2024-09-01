# spotify_manager.py
from minim import spotify


def get_spotify_client(client_id, client_secret):
    scopes = spotify.WebAPI.get_scopes("all")
    return spotify.WebAPI(client_id=client_id, client_secret=client_secret,
                          flow="pkce", scopes=scopes, web_framework="http.server")


def get_playlist_tracks(client, playlist_id):
    tracks = []
    results = client.get_playlist_items(playlist_id, limit=50)
    tracks.extend(results['items'])

    while results.get('next'):
        results = client.get_playlist_items(playlist_id, limit=50, offset=len(tracks))
        tracks.extend(results['items'])

    return tracks


def get_liked_songs(client):
    tracks = []
    results = client.get_saved_tracks(limit=50)
    tracks.extend(results['items'])

    while results.get('next'):
        results = client.get_saved_tracks(limit=50, offset=len(tracks))
        tracks.extend(results['items'])

    return tracks
