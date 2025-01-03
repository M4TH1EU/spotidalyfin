import streamlit as st

from spotidalyfin.managers.types import TrackQuality
from spotidalyfin.ui.helpers.getters import get_spotify_manager, get_tidal_manager


@st.cache_data(ttl=30)
def get_user_playlists(username: str) -> list[tuple[str, str]]:
    """Get all playlists for the given user."""
    return [(p.name, p.playlist_id) for p in get_spotify_manager(username).get_user_playlists()]

def download_playlist(playlist_id: str, spotify_account_username: str, tidal_account_username: str, quality: TrackQuality, output_type: str, destination: str):
    """Download a playlist from Spotify to TIDAL."""
    st.write(f"Downloading playlist {playlist_id} to TIDAL account {tidal_account_username} from Spotify account {spotify_account_username}.")

    spotify_manager = get_spotify_manager(spotify_account_username)
    tidal_manager = get_tidal_manager(tidal_account_username)

    spotify_playlist = spotify_manager.get_playlist(playlist_id, retrieve_all_tracks=True, retrieve_all_albums_details=False)
    print(spotify_playlist)

