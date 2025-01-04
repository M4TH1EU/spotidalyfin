import os

import streamlit as st

from spotidalyfin.db.helpers import get_authenticated_spotify_profiles, get_authenticated_tidal_profiles
from spotidalyfin.managers.types import TrackQuality
from spotidalyfin.ui.helpers.getters import get_database, get_spotify_manager, get_tidal_manager
from spotidalyfin.ui.helpers.platforms import get_user_playlists

# Initialize states
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
    st.session_state.completed = False

# Show input form (when not submitted)
if not st.session_state.submitted:
    st.header("Download playlist")
    st.write("Uses the Tidal API to download a playlist from Spotify in lossless quality.")

    logged_spotify_usernames = get_authenticated_spotify_profiles(get_database())
    logged_tidal_usernames = get_authenticated_tidal_profiles(get_database())

    if not logged_spotify_usernames or not logged_tidal_usernames:
        st.error("At least one Spotify and TIDAL account must be authenticated to download a playlist.")
        st.stop()

    # Form fields
    spotify_username = st.selectbox("Spotify Username:", logged_spotify_usernames)
    tidal_username = st.selectbox("Tidal Username:", logged_tidal_usernames)

    input_mode = st.radio(
        "How would you like to specify the playlist?",
        options=[("Select from account playlists", 0), ("Enter playlist ID/URL manually", 1)],
        format_func=lambda x: x[0],
    )

    with st.form("download_form"):
        # playlist_id = st.text_input("Playlist ID:")
        if input_mode[1] == 0:
            playlist_id = st.selectbox(
                "Select a playlist",
                options=get_user_playlists(spotify_username),
                format_func=lambda x: x[0]
            )
        else:
            playlist_id = st.text_input("Enter the playlist ID", value="")

        quality = st.radio(
            "Select the maximum quality you want to download",
            [
                ("320kbps", TrackQuality.LOW),
                ("FLAC", TrackQuality.LOSSLESS),
                (":rainbow[HiFi]", TrackQuality.HI_RES_LOSSLESS)
            ],
            format_func=lambda x: x[0],
            captions=[
                "Standard quality, small size",
                "Lossless quality, recommended",
                "High fidelity, larger file size."
            ],
            index=2
        )

        file_type = st.radio(
            "Select the output file type, does not affect quality or size",
            [(".flac", "flac"), (".m4a", "m4a")],
            format_func=lambda x: x[0],
            captions=["Better tags support (recommended)", "Embeds FLAC in MP4 container"],
            index=0
        )

        # Output destination
        output_dest = st.text_input("Output Destination:", os.path.expanduser("~/Music/Spotidalyfin"))

        # Submit button
        if st.form_submit_button("Download"):
            # Validate form data
            if not playlist_id or not output_dest or not spotify_username or not tidal_username or not quality or not file_type or not output_dest:
                st.error("Please fill in all the required fields.")
                st.stop()

            st.session_state.submitted = True
            # Store form data in session state
            st.session_state.form_data = {
                "spotify_username": spotify_username,
                "tidal_username": tidal_username,
                "playlist_id": playlist_id,
                "quality": quality,
                "file_type": file_type,
                "output_dest": output_dest
            }
            st.rerun()

# Show download progress (when submitted)
else:
    st.header("Downloading playlist")

    if isinstance(st.session_state.form_data['playlist_id'], tuple):
        playlist_id = st.session_state.form_data['playlist_id'][1]
    else:
        playlist_id = st.session_state.form_data['playlist_id']

    progress_bar = st.progress(0, "Download status")
    dev_infos = st.empty()
    status = st.status("")

    if not st.session_state.completed:
        # Display form data summary
        with dev_infos.expander("Development Info"):
            st.write("### Download Summary")
            st.write(f"Spotify Username: {st.session_state.form_data['spotify_username']}")
            st.write(f"Tidal Username: {st.session_state.form_data['tidal_username']}")
            st.write(f"Playlist ID: {st.session_state.form_data['playlist_id']}")
            st.write(f"Quality: {st.session_state.form_data['quality']}")
            st.write(f"File Type: {st.session_state.form_data['file_type']}")
            st.write(f"Output Destination: {st.session_state.form_data['output_dest']}")

        # Step 0
        msg = f":material/login: Initializing accounts managers..."
        status.update(label=msg, state="running", expanded=True)
        status.write(f"**{msg}**")
        spotify_manager = get_spotify_manager(st.session_state.form_data['spotify_username'])
        tidal_manager = get_tidal_manager(st.session_state.form_data['tidal_username'])

        status.divider()

        # Step 1
        msg = f":material/queue_music: Fetching Spotify playlist tracks..."
        status.update(label=msg, state="running", expanded=True)
        status.write(f"**{msg}**")
        spotify_playlist = spotify_manager.get_playlist(playlist_id)
        spotify_playlist_length = len(spotify_playlist.tracks)

        status.divider()

        # Step 2
        msg = f":material/compare_arrows: Matching Spotify tracks to TIDAL tracks..."
        status.update(label=msg, state="running", expanded=True)
        status.write(f"**{msg}**")
        tidal_playlist = tidal_manager.convert_spotify_playlist(spotify_playlist, status_container=status)
        tidal_playlist_length = len(tidal_playlist.tracks)

        status.divider()

        # Step 3
        msg = f":material/downloading: Downloading tracks..."
        status.update(label=msg, state="running", expanded=True)
        status.write(f"**{msg}**")
        tidal_manager.download_playlist(
            playlist=tidal_playlist,
            quality=st.session_state.form_data['quality'][1],
            output_type=st.session_state.form_data['file_type'][1],
            destination=st.session_state.form_data['output_dest'],
            status_container=status,
            progress_bar=progress_bar
        )

        st.session_state.completed = True

    # Show completion message and reset button
    status.update(label="Download Complete!", state="complete", expanded=False)
    st.success("All files have been downloaded successfully!")
    if st.button("Reset"):
        st.session_state.submitted = False
        st.session_state.completed = False
        st.rerun()
