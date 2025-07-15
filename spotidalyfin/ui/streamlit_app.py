import streamlit as st

from spotidalyfin.ui.helpers.getters import get_database


def setup_storage():
    """
    Initialize the main session state variables. This function should be called at the start of the app to ensure
    that all required session state variables are initialized.
    """
    if "spotify_managers" not in st.session_state:
        st.session_state.spotify_managers = {}
    if "tidal_managers" not in st.session_state:
        st.session_state.tidal_managers = {}

    get_database()  # Initializes the database and returns it


setup_storage()

home = st.Page("home.py", title="Home", icon=":material/home:", default=True)
# demo = st.Page("demo.py", title="Demo", icon=":material/insert_emoticon:")

home_pages = [home]

download_spotify_playlist = st.Page(
    "actions/download_playlist.py",
    title="Download playlists from TIDAL",
    icon=":material/download:"
)
spotify_sync_account = st.Page(
    "actions/sync_spotify_to_tidal.py",
    title=" Sync playlists to TIDAL",
    icon=":material/sync:"
)
spotify_pages = [download_spotify_playlist, spotify_sync_account]

tidal_sync_account = st.Page(
    "actions/sync_tidal_to_jellyfin.py",
    title="Sync playlists to Jellyfin",
    icon=":material/sync:"
)
tidal_pages = [tidal_sync_account]

account_settings = st.Page(
    "settings/accounts_settings.py",
    title="Account settings",
    icon=":material/manage_accounts:"
)
settings_pages = [account_settings]

st.logo("assets/ui/images/logo.webp", icon_image="assets/ui/images/icon.png", size="large")

page_dict = {
    "Home": home_pages,
    "Spotify": spotify_pages,
    "TIDAL": tidal_pages,
    "Settings": settings_pages,
}
pg = st.navigation(page_dict)
pg.run()
