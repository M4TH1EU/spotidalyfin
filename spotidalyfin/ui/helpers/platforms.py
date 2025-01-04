from spotidalyfin.ui.helpers.getters import get_spotify_manager


def get_user_playlists(username: str) -> list[tuple[str, str]]:
    """Get all playlists for the given user."""
    return [(p.name, p.playlist_id) for p in get_spotify_manager(username).get_user_playlists()]
