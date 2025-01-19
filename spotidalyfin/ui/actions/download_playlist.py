import os

import streamlit as st
from spotipy import SpotifyException

from spotidalyfin.db.helpers import get_authenticated_spotify_profiles, get_authenticated_tidal_profiles
from spotidalyfin.managers.types import TrackQuality
from spotidalyfin.ui.helpers.getters import get_database, get_spotify_manager, get_tidal_manager, \
    create_state_if_missing
from spotidalyfin.ui.helpers.platforms import get_user_playlists
from spotidalyfin.utils.logger import log

create_state_if_missing('download_playlist_submitted', False)
create_state_if_missing('download_playlist_completed', False)
create_state_if_missing('download_playlist_form_data', {})
create_state_if_missing('download_playlist_logs', [])

# Show input form (when not submitted)
if not st.session_state.download_playlist_submitted:
    # WARNING: no streamlit elements must be put here otherwise it messes with what is displayed

    with st.container():
        st.title(":material/download: Download playlist")
        st.write("Uses the Tidal API to download a playlist from Spotify in lossless quality.")

        logged_spotify_usernames = get_authenticated_spotify_profiles(get_database())
        logged_tidal_usernames = get_authenticated_tidal_profiles(get_database())

        if not logged_spotify_usernames or not logged_tidal_usernames:
            st.error("At least one Spotify and TIDAL account must be authenticated to download a playlist.")
            st.stop()

        # Form fields
        spotify_username = st.selectbox("Choose Spotify account to use for fetching playlist:",
                                        logged_spotify_usernames)
        tidal_username = st.selectbox("Choose TIDAL account to use for downloading:", logged_tidal_usernames)

        input_mode = st.radio(
            "How would you like to specify the playlist?",
            options=[("Select from account playlists", 0), ("Enter playlist ID/URL manually", 1)],
            format_func=lambda x: x[0],
        )

        with st.form("download_form"):
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
                    ("FLAC (lossless)", TrackQuality.LOSSLESS),
                    (":rainbow[HiFi]", TrackQuality.HI_RES_LOSSLESS)
                ],
                format_func=lambda x: x[0],
                captions=[
                    "Standard quality, small file size",
                    "Lossless quality, medium file size **(recommended)**",
                    "Maximum quality, large file size"
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

                st.session_state.download_playlist_submitted = True
                # Store form data in session state
                st.session_state.download_playlist_form_data = {
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

    # Normalize playlist ID (if from selectbox)
    if isinstance(st.session_state.download_playlist_form_data['playlist_id'], tuple):
        playlist_name = st.session_state.download_playlist_form_data['playlist_id'][0]
        playlist_id = st.session_state.download_playlist_form_data['playlist_id'][1]
    else:
        playlist_id = st.session_state.download_playlist_form_data['playlist_id']

    progress_bar = st.progress(0, "Waiting for download to start...")

    if not st.session_state.download_playlist_completed:
        # Display form data summary
        with st.expander(":material/bug_report: Development Info"):
            text = """
            Spotify Username: {spotify_username}
            Tidal Username: {tidal_username}
            Playlist ID: {playlist_id}
            Quality: {quality}
            File Type: {file_type}
            Output Destination: {output_dest}
            """.format(**st.session_state.download_playlist_form_data)
            st.code(text)

        # Download playlist and log progress
        with st.status("") as status:
            try:
                # Step 0
                msg = f":material/login: Initializing accounts managers..."
                status.update(label=msg, state="running", expanded=True)
                status.write(f"**{msg}**")
                spotify_manager = get_spotify_manager(st.session_state.download_playlist_form_data['spotify_username'])
                tidal_manager = get_tidal_manager(st.session_state.download_playlist_form_data['tidal_username'])

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
                st.session_state.download_playlist_logs = tidal_manager.download_playlist(
                    playlist=tidal_playlist,
                    quality=st.session_state.download_playlist_form_data['quality'][1],
                    output_type=st.session_state.download_playlist_form_data['file_type'][1],
                    destination=st.session_state.download_playlist_form_data['output_dest'],
                    status_container=status,
                    progress_bar=progress_bar
                )

                status.update(label="Download Complete!", state="complete", expanded=False)
                st.session_state.download_playlist_completed = True
            except SpotifyException as e:
                status.update(label="Spotify Error", state="error", expanded=False)
                st.error(f"An error occurred while fetching the playlist: {e}")
                log.error(f"An error occurred while fetching the playlist: {e}")
            # except Exception as e:
            #     status.update(label="Download Failed", state="error", expanded=False)
            #     st.error(f"An error occurred while downloading the playlist: {e}")
            #     log.error(f"An error occurred while downloading the playlist: {e}")

    # Show completion message and reset button
    if st.session_state.download_playlist_completed:

        # Display failed tracks if any
        failed_tracks = [log for log in st.session_state.download_playlist_logs if log[0] == False]
        if failed_tracks:
            st.warning(f"{len(failed_tracks)} tracks failed to download.", icon=":material/report:")
            with st.expander("Failed tracks", icon=":material/report:"):
                for log_status, log_track in failed_tracks:
                    st.write(f"{log_track.name} - {log_track.artist}")

        # status.update(label="Download Complete!", state="complete", expanded=False)
        st.success("All files have been downloaded successfully!")
        if st.button("Go back"):
            st.session_state.download_playlist_submitted = False
            st.session_state.download_playlist_completed = False
            st.session_state.download_playlist_form_data = {}
            st.session_state.download_playlist_logs = []
            st.rerun()
