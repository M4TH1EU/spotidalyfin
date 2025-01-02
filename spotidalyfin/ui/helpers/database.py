from typing import List

import streamlit as st

from spotidalyfin.db.database import Database


def get_database():
    if "database" not in st.session_state:
        st.session_state.database = Database()
    return st.session_state.database


def get_authenticated_spotify_profiles() -> List[tuple[str, str]]:
    """Get the authenticated Spotify profiles."""

    db = get_database()
    cursor = db.execute("SELECT client_id, username FROM spotify_accounts")
    return cursor.fetchall()


def remove_spotify_profile(username: str) -> None:
    """Remove a Spotify profile from the database."""
    db = get_database()
    db.execute("DELETE FROM spotify_accounts WHERE username=?", (username,))
    db.commit()
