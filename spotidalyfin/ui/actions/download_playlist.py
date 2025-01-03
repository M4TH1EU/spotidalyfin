import os

import streamlit as st

from spotidalyfin.db.helpers import get_authenticated_spotify_profiles, get_authenticated_tidal_profiles
from spotidalyfin.managers.types import TrackQuality
from spotidalyfin.ui.helpers.getters import get_database
from spotidalyfin.ui.helpers.platforms import get_user_playlists, download_playlist

if "currently_downloading" not in st.session_state:
    st.session_state["currently_downloading"] = False

if not st.session_state["currently_downloading"]:
    st.header("Download playlist")
    st.write("Uses the Tidal API to download a playlist from Spotify in lossless quality.")

    spotify_accounts = get_authenticated_spotify_profiles(get_database())
    tidal_accounts = get_authenticated_tidal_profiles(get_database())

    if not spotify_accounts or not tidal_accounts:
        st.error("Be sure to add at least one Spotify and TIDAL account in the settings.")
        st.stop()

    spotify_account = st.selectbox("Select a Spotify account", spotify_accounts)
    tidal_account = st.selectbox("Select a TIDAL account", tidal_accounts)

    st.subheader("Choose a playlist")
    list_of_playlists_choices = get_user_playlists(spotify_account)
    list_of_playlists_choices.insert(0, ("", ""))
    list_of_playlists_choices.insert(1, ("⚙️️️ Enter playlist ID manually", "other"))
    playlist = st.selectbox("Select a playlist", options=list_of_playlists_choices,
                            format_func=lambda x: x[0])
    if playlist[1] == "other":
        playlist = ("", st.text_input("Enter the playlist ID", value=""))

    st.subheader("Quality")
    quality = st.radio(
        "Select the maximum quality you want to download",
        [("320kbps", TrackQuality.LOW), ("FLAC", TrackQuality.LOSSLESS),
         (":rainbow[HiFi]", TrackQuality.HI_RES_LOSSLESS)],
        format_func=lambda x: x[0],
        captions=["Standard quality, small size", "Lossless quality, recommended", "High fidelity, larger file size."],
        index=2
    )

    st.subheader("Output file type")
    output_type = st.radio(
        "Select the output file type, does not affect quality or size",
        [(".flac", "flac"), (".m4a", "m4a")],
        format_func=lambda x: x[0],
        captions=["Better tags support (recommended)", "Embeds FLAC in MP4 container"],
        index=0
    )

    st.subheader("Destination")
    st.write("Choose a folder to save the downloaded playlist.")
    destination = st.text_input("Destination", os.path.expanduser("~/Music/Spotidalyfin"))

    download_button = st.button("Download playlist")
    if download_button:
        if playlist[1]:
            st.session_state["currently_downloading"] = True
            download_playlist(playlist_id=playlist[1], spotify_account_username=spotify_account,
                              tidal_account_username=tidal_account,
                              quality=quality[1], output_type=output_type[1], destination=destination)
            st.session_state["currently_downloading"] = False
        else:
            st.error("Please select a playlist to download.")

else:
    st.write("Currently downloading a playlist, please wait...")
