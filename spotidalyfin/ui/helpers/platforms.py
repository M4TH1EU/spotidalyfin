from spotidalyfin.managers.types import Platform
from spotidalyfin.ui.helpers.getters import get_manager_for_platform
from spotidalyfin.utils.logger import log


def get_user_playlists(username: str, platform: Platform) -> list[tuple[str, str]]:
    """Get all playlists for the given user."""
    try:
        manager = get_manager_for_platform(username, platform)

        playlists = [(p.name, p.id) for p in manager.get_user_playlists()]
        playlists.insert(0, ("Liked songs", "favorite_tracks"))

        return playlists
    except Exception as e:
        log.exception(f"Failed to get user playlists for {username}")
        return []
