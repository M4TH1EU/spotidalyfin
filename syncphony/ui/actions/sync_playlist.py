from typing import List, Tuple, Optional, Union

import streamlit as st

from syncphony.db.helpers import (
    get_authenticated_spotify_profiles,
    get_authenticated_tidal_profiles,
    get_authenticated_jellyfin_profiles,
    get_authenticated_subsonic_profiles,
)
from syncphony.models.enums import Platform
from syncphony.models.utils import get_track_on_another_platform
from syncphony.ui.helpers.getters import (
    get_database,
    create_state_if_missing,
    get_manager_for_platform,
)
from syncphony.utils.logger import log

PLATFORM_OPTIONS = [
    (Platform.SPOTIFY.value, Platform.SPOTIFY),
    (Platform.TIDAL.value, Platform.TIDAL),
    (Platform.JELLYFIN.value, Platform.JELLYFIN),
    (Platform.SUBSONIC.value, Platform.SUBSONIC),
]

ACCOUNT_FETCHERS = {
    Platform.SPOTIFY.value: get_authenticated_spotify_profiles,
    Platform.TIDAL.value: get_authenticated_tidal_profiles,
    Platform.JELLYFIN.value: get_authenticated_jellyfin_profiles,
    Platform.SUBSONIC.value: get_authenticated_subsonic_profiles,
}

DEFAULT_STATE = {
    "sync_account_submitted": False,
    "sync_account_completed": False,
    "sync_account_form_data": {},
    "sync_account_failed_tracks": [],
    "sync_account_failed_playlists_fetch": [],
    "sync_account_failed_playlists_create": [],
}

for key, value in DEFAULT_STATE.items():
    create_state_if_missing(key, value)


# @st.cache_data(show_spinner=False)
# def fetch_playlists_cached(platform: Platform, account: str, user: Optional[str]):
#     """Fetch and cache playlists for a given platform/account/user."""
#     manager = get_manager_for_platform(account, platform)
#     return manager.get_user_playlists(user_id=user if manager.is_multi_user() else None)

@st.cache_data(show_spinner=False)
def fetch_playlists_cached(platform: Platform, account: str, user: Optional[str]):
    """Fetch and cache playlists for a given platform/account/user."""
    manager = get_manager_for_platform(account, platform)
    return [
        {"name": p.name, "id": p.id} for p in
        manager.get_user_playlists(user_id=user if manager.is_multi_user() else None)
    ]


def select_platform_and_account(label_prefix: str) -> Tuple[Tuple[str, Platform], str, Optional[str]]:
    """Renders platform/account selection UI and returns chosen platform tuple, account, and optional user."""
    platform_choice = st.selectbox(
        f"Choose the platform to {label_prefix}:",
        options=PLATFORM_OPTIONS,
        format_func=lambda x: x[0],
        key=f"{label_prefix}_platform_select"

    )
    accounts = ACCOUNT_FETCHERS[platform_choice[0]](get_database())
    account_choice = st.selectbox(
        f"Choose {platform_choice[0]} account:",
        options=accounts,
        format_func=lambda x: x if isinstance(x, str) else f"{x[1]} ({x[0]})",
        key=f"{label_prefix}_account_select"
    )
    manager = get_manager_for_platform(account_choice, platform_choice[1])

    user_choice = None
    if manager.is_multi_user():
        users = manager.get_users()
        if users:
            selected_user = st.selectbox("Select user:", options=users, format_func=lambda x: x[1],
                                         key=f"{label_prefix}_user_select")
            user_choice = selected_user[0]

    return platform_choice, account_choice, user_choice


def display_failures():
    """Displays failed tracks/playlists after sync."""
    failures = {
        "tracks": ("tracks failed to sync", st.session_state.sync_account_failed_tracks,
                   lambda t: f"{t.name} - {t.artist}"),
        "playlists_fetch": ("playlists failed to fetch", st.session_state.sync_account_failed_playlists_fetch,
                            lambda p: f"{p[0]} (ID: {p[1]})"),
        "playlists_create": ("playlists failed to create", st.session_state.sync_account_failed_playlists_create,
                             lambda p: p.name),
    }
    any_failures = False

    for key, (msg, data, fmt) in failures.items():
        failed_items = [item for success, item in data if not success]
        if failed_items:
            any_failures = True
            st.warning(f"{len(failed_items)} {msg}.", icon=":material/report:")
            with st.expander(f"Details of {msg}", icon=":material/report:"):
                for item in failed_items:
                    st.write(fmt(item))

    if not any_failures:
        st.success("All playlists have been synced successfully!")
    else:
        st.warning("The sync process completed with some issues. Please review the logs above.")


def validate_and_prepare_playlists(from_manager, playlist_input: Union[str, List[Tuple[str, str]]]) -> List[
    Tuple[str, str]]:
    """Ensure playlists are in correct format before syncing."""
    if isinstance(playlist_input, str):
        playlist_obj = from_manager.get_playlist(playlist_input, fetch_tracks=False)
        return [(playlist_obj.name, playlist_obj.id)]
    return playlist_input


def sync_with_containers(from_manager, to_manager,
                         playlists: List[Tuple[str, str]],
                         from_user: Optional[str], to_user: Optional[str]):
    """Run sync for multiple playlists, each in its own container."""
    for playlist_name, playlist_id in playlists:
        with st.status(f"⏳ Fetching playlist `{playlist_name}`...", expanded=True) as status:
            playlist = from_manager.get_playlist(playlist_id, fetch_tracks=True)
            if not playlist:
                status.update(label=f"❌ Failed to fetch `{playlist_name}`", state="error", expanded=True)
                st.session_state.sync_account_failed_playlists_fetch.append((False, (playlist_name, playlist_id)))
                return

            # Track sync progress
            total_tracks = len(playlist.tracks)
            track_bar = st.progress(0, text=f"Syncing {total_tracks} tracks...")
            to_tracks = []

            status.update(label=f"🔄 Syncing tracks for `{playlist_name}`...", state="running", expanded=True)
            for idx, track in enumerate(playlist.tracks, start=1):
                track_bar.progress(idx / total_tracks,
                                   text=f"[{idx}/{total_tracks}] {track.name} - {track.artist.name}")
                to_track = get_track_on_another_platform(track, to_manager)
                if not to_track:
                    status.write(f"❌ Track not found: `{track.name} - {track.artist.name}`")
                    st.session_state.sync_account_failed_tracks.append((False, track))
                    continue
                to_tracks.append(to_track)
                status.write(f"✅ Synced: `{to_track.name} - {to_track.artist.name}`")

            track_bar.empty()

            if not to_tracks:
                status.update(label=f"⚠️ No tracks to sync for `{playlist.name}`", state="warning", expanded=True)
                return

            # Create playlist on destination
            status.update(label=f"📦 Creating `{playlist.name}` on {to_manager.PLATFORM.value}...", state="running",
                          expanded=True)
            to_playlist = to_manager.create_playlist(
                playlist.name, to_tracks, playlist.description, playlist.image, to_user
            )

            if not to_playlist:
                st.session_state.sync_account_failed_playlists_create.append((False, playlist))
                status.update(label=f"❌ Failed to create `{playlist.name}`", state="error", expanded=True)
            else:
                status.update(label=f"✅ Created `{to_playlist.name}` on {to_manager.PLATFORM.value}", state="complete",
                              expanded=False)


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

        # Source selection
        with st.container(border=1):
            st.subheader(":material/content_copy: Select source")
            from_select, from_account, from_user = select_platform_and_account("sync from")

            input_mode = st.radio(
                "What playlists would you like to sync?",
                options=[("All playlists", 0), ("Select playlists", 1), ("Enter playlist IDs manually", 2)],
                format_func=lambda x: x[0]
            )

            playlists = None
            if input_mode[1] in (0, 1):
                playlists_list = fetch_playlists_cached(from_select[1], from_account, from_user)
                playlists_tuples = [(p["name"], p["id"]) for p in playlists_list]
                playlists = playlists_tuples if input_mode[1] == 0 else st.multiselect(
                    "Select playlists to sync", options=playlists_tuples, format_func=lambda x: x[0]
                )
            elif input_mode[1] == 2:
                playlists = st.text_input("Enter the playlist ID", value="")

        # Destination selection
        with st.container(border=1):
            st.subheader(":material/content_paste: Select destination")
            to_select, to_account, to_user = select_platform_and_account("sync to")

        if from_select[1] == to_select[1]:
            st.error("Source and destination platforms must be different.")
            st.stop()

        # Submit form
        with st.form("sync_form"):
            if st.form_submit_button("Sync playlists"):
                if not playlists or not from_account or not to_account:
                    st.error("Please fill in all required fields.")
                    st.stop()

                st.session_state.sync_account_submitted = True
                st.session_state.sync_account_form_data = {
                    "from_platform": from_select[1],
                    "from_account": from_account,
                    "from_user": from_user,
                    "to_platform": to_select[1],
                    "to_account": to_account,
                    "to_user": to_user,
                    "playlists": playlists,
                }
                st.rerun()
else:
    st.header("Syncing playlist(s)...")

    if not st.session_state.sync_account_completed:
        try:
            form_data = st.session_state.sync_account_form_data
            from_manager = get_manager_for_platform(form_data["from_account"], form_data["from_platform"])
            to_manager = get_manager_for_platform(form_data["to_account"], form_data["to_platform"])

            prepared_playlists = validate_and_prepare_playlists(from_manager, form_data["playlists"])

            sync_with_containers(from_manager, to_manager, prepared_playlists,
                                 form_data.get("from_user"), form_data.get("to_user"))

            st.session_state.sync_account_completed = True
        except Exception as e:
            log.exception("Failed to sync playlists")
            st.error(f"An error occurred: {e}")

    display_failures()

    if st.button("Go back"):
        for key, value in DEFAULT_STATE.items():
            st.session_state[key] = value
        fetch_playlists_cached.clear()
        st.rerun()
