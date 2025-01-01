import streamlit as st

st.header("Download playlist")
st.write("Uses the Tidal API to download a playlist from Spotify in lossless quality.")

spotify_accounts = []
if not spotify_accounts:
    st.error("No Spotify accounts found. Please add one in the settings.")
    st.stop()

account = st.selectbox("Select a Spotify account", spotify_accounts)

st.subheader("Choose a playlist")
playlist = st.selectbox("Select a playlist", [])

st.subheader("Quality")
quality = st.radio(
    "Select the maximum quality you want to download",
    ["320kbps", "FLAC", ":rainbow[HiFi]"],
    captions=["Standard quality, small size", "Lossless quality, recommended", "High fidelity, larger file size."],
    index=1
)

st.subheader("Output file type")
output_type = st.radio(
    "Select the output file type, does not affect quality or size",
    [".flac", ".m4a"],
    captions=["Better tags support (recommended)", "Embeds FLAC in MP4 container"],
    index=0
)

if st.button("Download playlist"):
    st.write("Downloading...")
