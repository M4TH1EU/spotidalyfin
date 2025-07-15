import streamlit as st

from spotidalyfin.db.database import Database
from spotidalyfin.managers.jellyfin_manager import JellyfinManager
from spotidalyfin.managers.spotify_manager import SpotifyManager
from spotidalyfin.managers.tidal_manager import TidalManager


def get_database():
    if "database" not in st.session_state:
        st.session_state.database = Database()
    return st.session_state.database


def create_state_if_missing(key: str, value: any):
    if key not in st.session_state:
        st.session_state[key] = value
    # return st.session_state[key]


def get_spotify_manager(username: str) -> SpotifyManager:
    key = f"spotify_manager_{username}"
    if key not in st.session_state:
        st.session_state[key] = SpotifyManager(username, get_database())
    return st.session_state[key]


def get_tidal_manager(username: str) -> TidalManager:
    key = f"tidal_manager_{username}"
    if key not in st.session_state:
        st.session_state[key] = TidalManager(username, get_database())
    return st.session_state[key]

def get_jellyfin_manager(server: str) -> JellyfinManager:
    key = f"jellyfin_manager_{server}"
    if key not in st.session_state:
        st.session_state[key] = JellyfinManager(server, get_database())
    return st.session_state[key]
