from spotidalyfin import cfg
from spotidalyfin.managers.spotify_manager import SpotifyManager

def get_spotify_account() -> list[str]:
    return ["Account 1", "Account 2"]

def get_spotify_playlists(account: str) -> list[str]:
    if account == "Account 1":
        return ["Playlist 3", "Playlist 4", "Playlist 5"]
    else:
        return ["Playlist 1", "Playlist 2"]

# def _get_spotify() -> SpotifyManager:
#     return SpotifyManager(cfg.get("spotify_client_id"), cfg.get("spotify_client_secret"))