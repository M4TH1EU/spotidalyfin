import streamlit as st

from spotidalyfin.ui import api

st.header("Accounts settings")
st.write("Here you can manage all the accounts that you have added to Spotidalyfin.")


@st.dialog("Add Spotify account")
def add_spotify_account():
    st.info("Visit, if needed, https://developer.spotify.com/dashboard/applications to create a new Spotify application.")

    client_id = st.text_input("Client ID")
    client_secret = st.text_input("Client secret")
    spotify_username = st.text_input("Spotify username")

    if st.button("Add account"):
        api.connect_to_spotify(client_id, client_secret, spotify_username)

st.subheader("Spotify")
st.write("Here you can add or remove Spotify accounts.")
if st.button("Add Spotify account"):
    add_spotify_account()



st.subheader("TIDAL")
st.write("Here you can add or remove TIDAL accounts.")
if st.button("Add TIDAL account"):
    st.write("This feature is not yet implemented.")

