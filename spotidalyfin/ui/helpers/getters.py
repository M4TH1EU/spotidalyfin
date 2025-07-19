import streamlit as st

from spotidalyfin.db.database import Database
from spotidalyfin.engines.jellyfin_engine import JellyfinManager
from spotidalyfin.engines.spotify_engine import SpotifyManager
from spotidalyfin.engines.tidal_engine import TidalManager
from spotidalyfin.models.enums import Platform
from spotidalyfin.models.manager import Manager


def get_database():
    if "database" not in st.session_state:
        st.session_state.database = Database()
    return st.session_state.database


def create_state_if_missing(key: str, value: any):
    if key not in st.session_state:
        st.session_state[key] = value
    # return st.session_state[key]


def get_manager_for_platform(identifier: str, platform: Platform) -> Manager:
    """Get the manager for the given platform."""
    if platform == Platform.SPOTIFY:
        return get_spotify_manager(identifier)
    elif platform == Platform.TIDAL:
        return get_tidal_manager(identifier)
    elif platform == Platform.JELLYFIN:
        return get_jellyfin_manager(identifier)
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def get_spotify_manager(username: str) -> SpotifyManager:
    key = f"spotify_manager_{username}"
    if key not in st.session_state:
        st.session_state[key] = SpotifyManager(username=username, db=get_database())
    return st.session_state[key]


def get_tidal_manager(username: str) -> TidalManager:
    key = f"tidal_manager_{username}"
    if key not in st.session_state:
        st.session_state[key] = TidalManager(username=username, db=get_database())
    return st.session_state[key]


def get_jellyfin_manager(server: str) -> JellyfinManager:
    key = f"jellyfin_manager_{server}"
    if key not in st.session_state:
        st.session_state[key] = JellyfinManager(url=server, db=get_database())
    return st.session_state[key]
