from spotidalyfin.exceptions import UserPlaylistsException
from spotidalyfin.ui.helpers.getters import get_spotify_manager
from spotidalyfin.utils.logger import log


def get_user_playlists(username: str) -> list[tuple[str, str]]:
    """Get all playlists for the given user."""
    try:
        return [(p.name, p.playlist_id) for p in get_spotify_manager(username).get_user_playlists()]
    except UserPlaylistsException as e:
        log.exception(f"Failed to get user playlists for {username}")
        return []
