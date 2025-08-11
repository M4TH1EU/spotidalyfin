from typing import List

import streamlit as st

from spotidalyfin.db.helpers import get_authenticated_spotify_profiles, get_authenticated_tidal_profiles, \
    get_authenticated_jellyfin_profiles, get_authenticated_subsonic_profiles
from spotidalyfin.models.enums import Platform
from spotidalyfin.models.playlist import Playlist
from spotidalyfin.models.utils import get_track_on_another_platform
from spotidalyfin.ui.helpers.getters import get_database, create_state_if_missing, get_manager_for_platform
from spotidalyfin.utils.logger import log

create_state_if_missing('sync_account_submitted', False)
create_state_if_missing('sync_account_completed', False)
create_state_if_missing('sync_account_form_data', {})
create_state_if_missing('sync_account_failed_tracks', [])
create_state_if_missing('sync_account_failed_playlists_fetch', [])
create_state_if_missing('sync_account_failed_playlists_create', [])


@st.cache_data(show_spinner=False)
def fetch_playlists_cached(platform: Platform, account: str, user: str):
    manager = get_manager_for_platform(account, platform)
    return manager.get_user_playlists(user_id=user if manager.is_multi_user() else None)


if "page_loaded" not in st.session_state:
    # first time page loaded
    fetch_playlists_cached.clear()
    st.session_state.page_loaded = True

# Show input form (when not submitted)
if not st.session_state.sync_account_submitted:
    # WARNING: no streamlit elements must be put here otherwise it messes with what is displayed

    with st.container():
        st.title(":material/sync: Sync a playlist between two platforms")
        st.write("Syncs playlists between two platforms")

        platform_options = [
            (Platform.SPOTIFY.value, Platform.SPOTIFY),
            (Platform.TIDAL.value, Platform.TIDAL),
            (Platform.JELLYFIN.value, Platform.JELLYFIN),
            (Platform.SUBSONIC.value, Platform.SUBSONIC)
        ]
        accounts_options = {
            Platform.SPOTIFY.value: get_authenticated_spotify_profiles(get_database()),
            Platform.TIDAL.value: get_authenticated_tidal_profiles(get_database()),
            Platform.JELLYFIN.value: get_authenticated_jellyfin_profiles(get_database()),
            Platform.SUBSONIC.value: get_authenticated_subsonic_profiles(get_database())
        }

        with st.container(border=1):
            st.subheader(":material/content_copy: Select source platform and account")

            from_select = st.selectbox(
                "Choose the platform to sync from:",
                options=platform_options,
                format_func=lambda x: x[0]
            )
            from_account = st.selectbox(
                f"Choose {from_select[0]} account to use for fetching playlists:",
                options=accounts_options[from_select[0]],
                format_func=lambda x: x if isinstance(x, str) else f"{x[1]} ({x[0]})"
            )

            from_manager = get_manager_for_platform(from_account, from_select[1])

            from_user = None
            if from_manager.is_multi_user():
                from_users = from_manager.get_users()
                if from_users:
                    from_user_select = st.selectbox(
                        "Select user:",
                        options=from_users,
                        format_func=lambda x: x[1],
                    )
                    from_user = from_user_select[0]

            input_mode = st.radio(
                "What playlists would you like to sync?",
                options=[("All playlists", 0), ("Select playlists", 1), ("Enter playlist IDs manually", 2)],
                format_func=lambda x: x[0],
            )
            cache_key = f"{from_account}_{from_user}"

            # Use a cache key based on platform, account, user
            if input_mode[1] in (0, 1):
                with st.spinner("Loading playlists (this may take a while)..."):
                    playlists = fetch_playlists_cached(from_select[1], from_account, from_user)
                    playlists_tuples = [(p.name, p.id) for p in playlists]

                if input_mode[1] == 0:
                    playlists = playlists_tuples
                else:
                    playlists = st.multiselect(
                        "Select playlists to sync",
                        options=playlists_tuples,
                        format_func=lambda x: x[0],
                        key="playlists_multiselect"
                    )
            elif input_mode[1] == 2:
                playlists = st.text_input("Enter the playlist ID", value="", key="playlist_manual")
            else:
                st.error("Invalid input mode.")
                st.stop()

        with st.container(border=1):
            st.subheader(":material/content_paste: Select destination platform and account")

            to_select = st.selectbox(
                "Choose the platform to sync to:",
                options=platform_options,
                format_func=lambda x: x[0]
            )
            to_account = st.selectbox(
                f"Choose {to_select[0]} account to sync the playlists to:",
                options=accounts_options[to_select[0]],
                format_func=lambda x: x if isinstance(x, str) else f"{x[1]} ({x[0]})"
            )

            to_manager = get_manager_for_platform(to_account, to_select[1])
            if to_manager.is_multi_user():
                to_users = to_manager.get_users()
                if to_users:
                    to_user_select = st.selectbox(
                        "Select user:",
                        options=to_users,
                        format_func=lambda x: x[1]
                    )
                    to_user = to_user_select[0]

        if from_select[1] == to_select[1]:
            st.error("Source and destination platforms must be different.")
            st.stop()

        with st.form("sync_form", border=input_mode[1] != 0):

            # Submit button
            if st.form_submit_button("Sync playlists"):
                # Validate form data
                if not playlists or not from_account or not to_account:
                    st.error("Please fill in all the required fields.")
                    st.stop()

                st.session_state.sync_account_submitted = True
                # Store form data in session state
                st.session_state.sync_account_form_data = {
                    "from_platform": from_select[1],
                    "from_account": from_account,
                    "from_user": from_user if from_manager.is_multi_user() else None,
                    "to_platform": to_select[1],
                    "to_account": to_account,
                    "to_user": to_user if to_manager.is_multi_user() else None,
                    "playlists": playlists,
                }
                st.rerun()

# Show download progress (when submitted)
else:
    st.header("Syncing playlist(s)...")

    if not st.session_state.sync_account_completed:
        # Display form data summary
        with st.expander(":material/bug_report: Development Info"):
            text = """
From Platform: {from_platform}
From Account: {from_account}
To Platform: {to_platform}
To Account: {to_account}
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

                from_manager = get_manager_for_platform(
                    st.session_state.sync_account_form_data['from_account'],
                    st.session_state.sync_account_form_data['from_platform']
                )
                to_manager = get_manager_for_platform(
                    st.session_state.sync_account_form_data['to_account'],
                    st.session_state.sync_account_form_data['to_platform']
                )
                from_user = st.session_state.sync_account_form_data.get('from_user', None)
                to_user = st.session_state.sync_account_form_data.get('to_user', None)

                # Step 1
                msg = f":material/queue_music: Making sure playlists format is correct..."
                status.update(label=msg, state="running", expanded=True)
                status.write(f"**{msg}**")

                if isinstance(st.session_state.sync_account_form_data['playlists'], str):
                    playlist_name = from_manager.get_playlist(st.session_state.sync_account_form_data['playlists'],
                                                              fetch_tracks=False).name
                    playlists = [(st.session_state.sync_account_form_data['playlists'], playlist_name)]
                else:
                    playlists = st.session_state.sync_account_form_data['playlists']

                if not playlists:
                    st.error("No playlists selected or provided.")
                    st.stop()

                # Step 2
                msg = f":material/queue_music: Fetching playlists from {st.session_state.sync_account_form_data['from_platform'].value}..."
                status.update(label=msg, state="running", expanded=True)
                status.write(f"**{msg}**")
                from_playlists: List[Playlist] = []

                for playlist in playlists:
                    from_playlist = from_manager.get_playlist(playlist[1], fetch_tracks=True)
                    if not from_playlist:
                        st.error(f":red[-> Failed to fetch playlist: `{playlist[0]}`]")
                        st.session_state.sync_account_failed_playlists_fetch.append((False, playlist))
                        continue

                    from_playlists.append(from_playlist)
                    status.write(f":green[-> Fetched playlist: {playlist[0]}]")

                status.divider()

                # Step 3
                msg = f":material/compare_arrows: Syncing playlists to {st.session_state.sync_account_form_data['to_platform'].value}..."
                status.update(label=msg, state="running", expanded=True)
                status.write(f"**{msg}**")

                for from_playlist in from_playlists:
                    status.write(f":material/playlist_add: Starting sync for playlist: {from_playlist.name}")
                    to_tracks = []
                    for track in from_playlist.tracks:
                        track_status_container = status.empty()

                        track_status_container.write(
                            f":material/music_note: Syncing track: {track.name} - {track.artist.name}")
                        to_track = get_track_on_another_platform(track, to_manager)
                        if not to_track:
                            status.write(
                                f":red[-> Track not found on {to_manager.PLATFORM.value}: {track.name} - {track.artist.name}]")
                            st.session_state.sync_account_failed_tracks.append((False, track))
                            continue
                        to_tracks.append(to_track)
                        track_status_container.write(
                            f":green[-> Track synced: {to_track.name} - {to_track.artist.name}]")

                    if not to_tracks:
                        status.write(f":red[-> No tracks found to sync for playlist: {from_playlist.name}]")
                        continue

                    status.write(
                        f":material/playlist_add: Creating playlist on {to_manager.PLATFORM.value}: {from_playlist.name}")
                    to_playlist = to_manager.create_playlist(from_playlist.name, to_tracks, from_playlist.description,
                                                             from_playlist.image, to_user)
                    if not to_playlist:
                        status.write(f":red[-> Failed to create playlist: {from_playlist.name}]")
                        continue

                    status.write(f":green[-> Created playlist: {to_playlist.name}]")
                    status.divider()

                status.update(label="Sync Complete!", state="complete", expanded=False)
                st.session_state.sync_account_completed = True


            except Exception as e:
                log.exception("Failed to sync playlists")
                st.error(f"An error occurred while syncing playlists: {e}")

    # Show completion message and reset button
    if st.session_state.sync_account_completed:
        # Display failed tracks if any
        failed_tracks = [log for log in st.session_state.sync_account_failed_tracks if log[0] == False]
        failed_playlists_fetch = [log for log in st.session_state.sync_account_failed_playlists_fetch if
                                  log[0] == False]
        failed_playlists_create = [log for log in st.session_state.sync_account_failed_playlists_create if
                                   log[0] == False]

        if failed_tracks:
            st.warning(f"{len(failed_tracks)} tracks failed to sync.", icon=":material/report:")
            with st.expander("No match found for the following tracks", icon=":material/report:"):
                for log_status, log_track in failed_tracks:
                    st.write(f"{log_track.name} - {log_track.artist}")
        if failed_playlists_fetch:
            st.warning(f"{len(failed_playlists_fetch)} playlists failed to fetch.", icon=":material/report:")
            with st.expander("The following playlists failed to fetch", icon=":material/report:"):
                for log_status, log_playlist in failed_playlists_fetch:
                    st.write(f"{log_playlist[0]} (ID: {log_playlist[1]})")
        if failed_playlists_create:
            st.warning(f"{len(failed_playlists_create)} playlists failed to create.", icon=":material/report:")
            with st.expander("The following playlists failed to create", icon=":material/report:"):
                for log_status, log_playlist in failed_playlists_create:
                    st.write(f"{log_playlist.name}")

        if not failed_tracks and not failed_playlists_fetch and not failed_playlists_create:
            st.success("All playlists have been synced successfully!")
        else:
            st.warning("The sync process has completed with some issues. Please review the logs above.")

        if st.button("Go back"):
            st.session_state.sync_account_submitted = False
            st.session_state.sync_account_completed = False
            st.session_state.sync_account_form_data = {}
            st.session_state.sync_account_failed_tracks = []
            st.session_state.sync_account_failed_playlists_fetch = []
            st.session_state.sync_account_failed_playlists_create = []
            fetch_playlists_cached.clear()
            st.rerun()
