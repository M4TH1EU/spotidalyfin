import streamlit as st

from spotidalyfin.managers.types import TrackQuality
from spotidalyfin.ui.helpers.getters import get_spotify_manager, get_tidal_manager


@st.cache_data(ttl=30)
def get_user_playlists(username: str) -> list[tuple[str, str]]:
    """Get all playlists for the given user."""
    return [(p.name, p.playlist_id) for p in get_spotify_manager(username).get_user_playlists()]


def download_playlist(playlist_id: str, spotify_account_username: str, tidal_account_username: str,
                      quality: TrackQuality, output_type: str, destination: str):
    """Download a playlist from Spotify to TIDAL."""

    with st.status("") as status:
        def _update(label: str, state: str = "running", expanded: bool = False):
            st.write(label)
            status.update(label=label, state=state, expanded=expanded)

        _update("Initializing accounts managers...")
        try:
            spotify_manager = get_spotify_manager(spotify_account_username)
            tidal_manager = get_tidal_manager(tidal_account_username)
        except Exception as e:
            status.update(
                label=f"Failed to initialize account managers: {e}",
                state="error",
                expanded=True
            )
            return

        _update("Fetching Spotify playlist tracks...")
        try:
            spotify_playlist = spotify_manager.get_playlist(playlist_id)
        except Exception as e:
            status.update(
                label=f"Failed to fetch playlist tracks: {e}",
                state="error",
                expanded=True
            )
            return

        _update("Matching Spotify tracks to TIDAL tracks...")
        try:
            tidal_playlist = tidal_manager.convert_spotify_playlist(spotify_playlist)
        except Exception as e:
            status.update(
                label=f"Failed to convert Spotify playlist: {e}",
                state="error",
                expanded=True
            )
            return

        _update("Downloading tracks...")
        try:
            tidal_manager.download_playlist(
                playlist=tidal_playlist,
                quality=quality,
                output_type=output_type,
                destination=destination,
            )
        except Exception as e:
            status.update(
                label=f"Failed to download playlist: {e}",
                state="error",
                expanded=True
            )
            return

        _update("Download complete!", state="success", expanded=False)
