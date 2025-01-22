import streamlit as st
from spotipy import SpotifyException

from spotidalyfin.db.helpers import get_authenticated_spotify_profiles, get_authenticated_tidal_profiles
from spotidalyfin.ui.helpers.getters import get_database, get_spotify_manager, get_tidal_manager, \
    create_state_if_missing
from spotidalyfin.ui.helpers.platforms import get_user_playlists
from spotidalyfin.utils.logger import log

create_state_if_missing('sync_account_submitted', False)
create_state_if_missing('sync_account_completed', False)
create_state_if_missing('sync_account_form_data', {})
create_state_if_missing('sync_account_logs', [])

# Show input form (when not submitted)
if not st.session_state.sync_account_submitted:
    # WARNING: no streamlit elements must be put here otherwise it messes with what is displayed

    with st.container():
        st.title(":material/sync: Sync account playlists")
        st.write("Syncs playlists from Spotify to TIDAL accounts.")
        st.info("*2-way synchronization might be implemented in the future.*")

        logged_spotify_usernames = get_authenticated_spotify_profiles(get_database())
        logged_tidal_usernames = get_authenticated_tidal_profiles(get_database())

        if not logged_spotify_usernames or not logged_tidal_usernames:
            st.error("At least one Spotify and TIDAL account must be authenticated to download a playlist.")
            st.stop()

        # Form fields
        spotify_username = st.selectbox("Choose Spotify account to use for fetching playlists:",
                                        logged_spotify_usernames)
        tidal_username = st.selectbox("Choose TIDAL account to sync the playlists to:", logged_tidal_usernames)

        input_mode = st.radio(
            "What playlists would you like to sync?",
            options=[("All playlists", 0), ("Select playlists", 1), ("Enter playlist IDs manually", 2)],
            format_func=lambda x: x[0],
        )

        with st.form("sync_form", border=input_mode[1] != 0):
            match input_mode[1]:
                case 0:
                    playlists = get_user_playlists(spotify_username)
                case 1:
                    playlists = st.multiselect(
                        "Select playlists to sync",
                        options=get_user_playlists(spotify_username),
                        format_func=lambda x: x[0]
                    )
                case 2:
                    playlists = st.text_input("Enter the playlist ID", value="")
                case _:
                    st.error("Invalid input mode.")
                    st.stop()

            # Submit button
            if st.form_submit_button("Sync playlists"):
                # Validate form data
                if not playlists or not spotify_username or not tidal_username:
                    st.error("Please fill in all the required fields.")
                    st.stop()

                st.session_state.sync_account_submitted = True
                # Store form data in session state
                st.session_state.sync_account_form_data = {
                    "spotify_username": spotify_username,
                    "tidal_username": tidal_username,
                    "playlists": playlists,
                }
                st.rerun()

# Show download progress (when submitted)
else:
    st.header("Syncing playlist(s)...")

    # Normalize playlists list
    if isinstance(st.session_state.sync_account_form_data['playlists'], str):
        playlist_name = get_spotify_manager(st.session_state.sync_account_form_data['spotify_username']).get_playlist(
            st.session_state.sync_account_form_data['playlists']).name
        playlists = [(st.session_state.sync_account_form_data['playlists'], playlist_name)]
    else:
        playlists = st.session_state.sync_account_form_data['playlists']

    if not st.session_state.sync_account_completed:
        # Display form data summary
        with st.expander(":material/bug_report: Development Info"):
            text = """
            Spotify Username: {spotify_username}
            Tidal Username: {tidal_username}
            Playlists: {playlists}
            """.format(**st.session_state.sync_account_form_data)
            st.code(text)

        # Sync playlists and log progress
        with st.status("") as status:
            try:
                # Step 0
                msg = f":material/login: Initializing accounts managers..."
                status.update(label=msg, state="running", expanded=True)
                status.write(f"**{msg}**")
                spotify_manager = get_spotify_manager(st.session_state.sync_account_form_data['spotify_username'])
                tidal_manager = get_tidal_manager(st.session_state.sync_account_form_data['tidal_username'])

                # Step 1
                msg = f":material/queue_music: Fetching Spotify playlist tracks..."
                status.update(label=msg, state="running", expanded=True)
                status.write(f"**{msg}**")
                spotify_playlists = []
                for playlist in playlists:
                    spotify_playlist = spotify_manager.get_playlist(playlist[1])
                    if not spotify_playlist:
                        st.error(f":red[-> Failed to fetch playlist: `{playlist[0]}`]")
                    spotify_playlists.append(spotify_playlist)
                    status.write(f":green[-> Fetched playlist: {playlist[0]}]")

                status.divider()

                # Step 2
                msg = f":material/compare_arrows: Syncing Spotify playlists to TIDAL..."
                status.update(label=msg, state="running", expanded=True)
                status.write(f"**{msg}**")
                for spotify_playlist in spotify_playlists:
                    status.write(f"**{spotify_playlist.name}**")
                    tidal_playlist = tidal_manager.convert_spotify_playlist(spotify_playlist, only_ids=True,
                                                                            status_container=status)
                    tidal_manager.create_playlist(tidal_playlist)
                    status.write(f"**Synced playlist : {spotify_playlist.name}**")
                    status.divider()

                status.update(label="Sync Complete!", state="complete", expanded=False)
                st.session_state.sync_account_completed = True
            except SpotifyException as e:
                status.update(label="Spotify Error", state="error", expanded=False)
                st.error(f"An error occurred while fetching the playlist: {e}")
                log.error(f"An error occurred while fetching the playlist: {e}")

    # Show completion message and reset button
    if st.session_state.sync_account_completed:
        # Display failed tracks if any
        failed_tracks = [log for log in st.session_state.sync_account_logs if log[0] == False]
        if failed_tracks:
            st.warning(f"{len(failed_tracks)} tracks failed to sync.", icon=":material/report:")
            with st.expander("Failed tracks", icon=":material/report:"):
                for log_status, log_track in failed_tracks:
                    st.write(f"{log_track.name} - {log_track.artist}")

        st.success("All playlists have been synced successfully!")
        if st.button("Go back"):
            st.session_state.sync_account_submitted = False
            st.session_state.sync_account_completed = False
            st.session_state.sync_account_form_data = {}
            st.session_state.sync_account_logs = []
            st.rerun()
