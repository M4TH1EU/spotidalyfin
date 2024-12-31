import spotipy
from spotipy import SpotifyOAuth

from spotidalyfin.db.spotipy import SpotidalyfinSpotifyDatabaseCache


def get_spotify_account() -> list[str]:
    return ["Account 1", "Account 2"]


def connect_to_spotify(client_id, client_secret, username):
    scopes = [
        'playlist-read-private',
        'playlist-read-collaborative',
        'user-library-read'
    ]

    spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="http://127.0.0.1:6969",
            scope=scopes,
            open_browser=False,
            cache_handler=SpotidalyfinSpotifyDatabaseCache(db, client_id, client_secret, username)
        )
    )


def get_spotify_playlists(account: str) -> list[str]:
    if account == "Account 1":
        return ["Playlist 3", "Playlist 4", "Playlist 5"]
    else:
        return ["Playlist 1", "Playlist 2"]

# def _get_spotify() -> SpotifyManager:
#     return SpotifyManager(cfg.get("spotify_client_id"), cfg.get("spotify_client_secret"))
