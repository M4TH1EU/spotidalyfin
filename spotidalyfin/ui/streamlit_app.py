import streamlit as st

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
