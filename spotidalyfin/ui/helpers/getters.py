import streamlit as st

from spotidalyfin.db.database import Database


def get_database():
    if "database" not in st.session_state:
        st.session_state.database = Database()
    return st.session_state.database

# def get_spotify_manager(client_id: str, client_secret: str, username: str) -> SpotifyManager:
#     key = f"{username}_{client_id}"  # Unique key for the account
#     if key not in st.session_state.spotify_managers:
#         st.session_state.spotify_managers[key] = SpotifyManager(client_id, client_secret, username, get_database())
#     return st.session_state.spotify_managers[key]
