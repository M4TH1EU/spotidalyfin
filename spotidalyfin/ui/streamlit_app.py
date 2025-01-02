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
demo = st.Page("demo.py", title="Demo", icon=":material/insert_emoticon:")

home_pages = [home, demo]

download_playlist = st.Page(
    "actions/download_playlist.py",
    title="Download playlist",
    icon=":material/download:"
)
actions_pages = [download_playlist]

account_settings = st.Page(
    "settings/accounts_settings.py",
    title="Account settings",
    icon=":material/manage_accounts:"
)
settings_pages = [account_settings]

st.logo("assets/ui/images/logo.webp", icon_image="assets/ui/images/icon.png", size="large")

page_dict = {
    "Home": home_pages,
    "Actions": actions_pages,
    "Settings": settings_pages,
}
pg = st.navigation(page_dict)
pg.run()
