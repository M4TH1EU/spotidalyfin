from spotidalyfin.exceptions import UserPlaylistsException
from spotidalyfin.managers.types import Platform
from spotidalyfin.ui.helpers.getters import get_spotify_manager, get_tidal_manager
from spotidalyfin.utils.logger import log


def get_user_playlists(username: str, platform: Platform) -> list[tuple[str, str]]:
    """Get all playlists for the given user."""
    try:
        playlists = []

        if platform == Platform.SPOTIFY:
            playlists = [(p.name, p.id) for p in get_spotify_manager(username).get_user_playlists()]
            playlists.insert(0, ("Liked songs", "favorite_tracks"))
        elif platform == Platform.TIDAL:
            playlists = [(p.name, p.playlist_id) for p in get_tidal_manager(username).get_user_playlists()]
            playlists.insert(0, ("Liked songs", "liked_songs"))

        return playlists
    except UserPlaylistsException as e:
        log.exception(f"Failed to get user playlists for {username}")
        return []
