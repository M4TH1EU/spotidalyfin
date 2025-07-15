import streamlit as st
from spotipy import SpotifyException

from spotidalyfin.db.helpers import get_authenticated_spotify_profiles, get_authenticated_tidal_profiles, \
    get_authenticated_jellyfin_profiles
from spotidalyfin.managers.types import Platform
from spotidalyfin.ui.helpers.getters import get_database, get_spotify_manager, get_tidal_manager, \
    create_state_if_missing, get_jellyfin_manager
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
        st.title(":material/sync: Sync TIDAL playlists to Jellyfin")
        st.write("Syncs playlists from TIDAL to a Jellyfin server.")

        logged_tidal_usernames = get_authenticated_tidal_profiles(get_database())
        logged_jellyfin_servers = get_authenticated_jellyfin_profiles(get_database())

        if not logged_jellyfin_servers or not logged_tidal_usernames:
            st.error("At least one Spotify and TIDAL account must be authenticated to download a playlist.")
            st.stop()

        # Form fields
        tidal_username = st.selectbox("Choose TIDAL account to use for fetching playlists:", logged_tidal_usernames)

        jellyfin_server = st.selectbox("Choose a Jellyfin server to sync the playlists to:",
                                        logged_jellyfin_servers)

        jellyfin_user = None
        if jellyfin_server:
            jellyfin_user = st.selectbox("Choose a Jellyfin user to sync the playlists to:", get_jellyfin_manager(jellyfin_server).get_users(only_names=True))


        input_mode = st.radio(
            "What playlists would you like to sync?",
            options=[("All playlists", 0), ("Select playlists", 1), ("Enter playlist IDs manually", 2)],
            format_func=lambda x: x[0],
        )

        with st.form("sync_form", border=input_mode[1] != 0):
            match input_mode[1]:
                case 0:
                    playlists = get_user_playlists(tidal_username, Platform.TIDAL)
                case 1:
                    playlists = st.multiselect(
                        "Select playlists to sync",
                        options=get_user_playlists(tidal_username, Platform.TIDAL),
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
                if not playlists or not tidal_username or not tidal_username:
                    st.error("Please fill in all the required fields.")
                    st.stop()

                st.session_state.sync_account_submitted = True
                # Store form data in session state
                st.session_state.sync_account_form_data = {
                    "tidal_username": tidal_username,
                    "jellyfin_url": jellyfin_server,
                    "jellyfin_user": jellyfin_user,
                    "playlists": playlists,
                }
                st.rerun()

# Show download progress (when submitted)
else:
    st.header("Syncing playlist(s)...")

    # Normalize playlists list
    if isinstance(st.session_state.sync_account_form_data['playlists'], str):
        playlist_name = get_tidal_manager(st.session_state.sync_account_form_data['tidal_username']).get_playlist(playlist_id=st.session_state.sync_account_form_data['playlists']).name
        playlists = [(st.session_state.sync_account_form_data['playlists'], playlist_name)]
    else:
        playlists = st.session_state.sync_account_form_data['playlists']

    if not st.session_state.sync_account_completed:
        # Display form data summary
        with st.expander(":material/bug_report: Development Info"):
            text = """
            Tidal Username: {tidal_username}
            Jellyfin Server: {jellyfin_url}
            Jellyfin Username: {jellyfin_user}

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
                tidal_manager = get_tidal_manager(st.session_state.sync_account_form_data['tidal_username'])
                jellyfin_manager = get_jellyfin_manager(st.session_state.sync_account_form_data['jellyfin_url'])

                # Step 1
                msg = f":material/queue_music: Fetching TIDAL playlist tracks..."
                status.update(label=msg, state="running", expanded=True)
                status.write(f"**{msg}**")
                tidal_playlists = []
                for playlist in playlists:
                    tidal_playlist = tidal_manager.get_playlist(playlist[1], retrieve_all_tracks=True)
                    if not tidal_playlist:
                        st.error(f":red[-> Failed to fetch playlist: `{playlist[0]}`]")
                    tidal_playlists.append(tidal_playlist)
                    status.write(f":green[-> Fetched playlist: {playlist[0]}]")

                status.divider()

                # Step 2
                msg = f":material/compare_arrows: Syncing TIDAL playlists to Jellyfin..."
                status.update(label=msg, state="running", expanded=True)
                status.write(f"**{msg}**")
                for tidal_playlist in tidal_playlists:
                    status.write(f"**{tidal_playlist.name}**")
                    jellyfin_playlist = jellyfin_manager.convert_tidal_playlist(tidal_playlist, status_container=status)
                    playlist = tidal_manager.create_playlist(jellyfin_playlist)
                    if playlist:
                        status.write(f"**Synced playlist : {tidal_playlist.name}**")
                    else:
                        status.write(f"**Failed to sync playlist : {tidal_playlist.name}**")
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
