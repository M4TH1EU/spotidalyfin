import streamlit as st

from spotidalyfin.ui.helpers.database import get_authenticated_spotify_profiles
from spotidalyfin.ui.helpers.spotify import get_spotify_manager
from spotidalyfin.ui.helpers.ui import display_subheader_with_icon, create_aligned_columns


# Callback to update the current step
def go_to_step(step):
    """Update the current step."""
    st.session_state.spot_dialog["step"] = step


@st.dialog("Spotify Connection")
def spotify_connection_dialog():
    """Multi-step Spotify connection dialog."""

    # Initialize session state variables
    if "spot_dialog" not in st.session_state:
        st.session_state.spot_dialog = {"step": 1, "client_id": "", "client_secret": "", "spotify_username": "",
                                        "redirect_url": "", "spotify_login_error": "", "finished": False, }

    if st.session_state.spot_dialog["step"] == 1:
        # Step 1: Collect Spotify App credentials
        st.subheader("Step 1: Provide Spotify App Details")
        st.info("Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications) "
                "to create a new Spotify application if needed.")

        st.session_state.spot_dialog["client_id"] = st.text_input("Client ID",
                                                                  value=st.session_state.spot_dialog["client_id"])
        st.session_state.spot_dialog["client_secret"] = st.text_input("Client Secret",
                                                                      value=st.session_state.spot_dialog[
                                                                          "client_secret"], type="password")
        st.session_state.spot_dialog["spotify_username"] = st.text_input("Spotify Username",
                                                                         value=st.session_state.spot_dialog[
                                                                             "spotify_username"])

        def _next_button_callback():
            if not st.session_state.spot_dialog["client_id"] or not st.session_state.spot_dialog["client_secret"] or not \
                    st.session_state.spot_dialog["spotify_username"]:
                st.session_state.spot_dialog["spotify_login_error"] = "Please fill in all fields to continue."
            elif st.session_state.spot_dialog["spotify_username"] in [x[1] for x in
                                                                      get_authenticated_spotify_profiles()]:
                st.session_state.spot_dialog["spotify_login_error"] = "This account is already authenticated."
            # elif get_spotify_manager(
            #         st.session_state.client_id,
            #         st.session_state.client_secret,
            #         st.session_state.spotify_username).is_authenticated():
            #     st.error("This account is already connected.")
            else:
                st.session_state.spot_dialog["spotify_login_error"] = ""
                go_to_step(2)

        if st.session_state.spot_dialog["spotify_login_error"]:
            st.error(st.session_state.spot_dialog["spotify_login_error"])

        st.button("Next", on_click=_next_button_callback)

    elif st.session_state.spot_dialog["step"] == 2:
        # Step 2: Show authorization URL and accept code
        st.subheader("Step 2: Authorize Spotidalyfin")
        st.info("Visit the following URL to authorize Spotidalyfin to access your Spotify account.")

        # Generate the authorization URL (adjust `api` call as needed)
        auth_url = get_spotify_manager(st.session_state.spot_dialog["client_id"],
                                       st.session_state.spot_dialog["client_secret"],
                                       st.session_state.spot_dialog["spotify_username"]).authorize_url

        st.markdown(f"[Authorize Spotify]({auth_url})", unsafe_allow_html=True)

        # Input for the redirect URL
        st.session_state.spot_dialog["redirect_url"] = st.text_input(
            "Enter the URL you were redirected to after authorization.")

        def _connect_button_callback():
            if not st.session_state.spot_dialog["redirect_url"]:
                st.error("Please enter the URL you were redirected to after authorizing Spotidalyfin.")
            else:
                # Call the API to connect with the code
                success = get_spotify_manager(st.session_state.spot_dialog["client_id"],
                                              st.session_state.spot_dialog["client_secret"],
                                              st.session_state.spot_dialog["spotify_username"]).authenticate(
                    st.session_state.spot_dialog["redirect_url"])

                if success:
                    st.success("Successfully connected to Spotify!")
                    go_to_step(3)
                else:
                    st.error("Failed to connect. Please check your authorization code.")

        st.button("Connect", on_click=_connect_button_callback)

    elif st.session_state.spot_dialog["step"] == 3:
        # Step 3: Completion
        st.subheader("Step 3: Setup Complete!")
        st.success("Your Spotify account has been successfully connected.")

        st.session_state.spot_dialog["client_id"] = ""
        st.session_state.spot_dialog["client_secret"] = ""
        st.session_state.spot_dialog["spotify_username"] = ""
        st.session_state.spot_dialog["redirect_url"] = ""
        st.session_state.spot_dialog["finished"] = True

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Close", icon=":material/close:", use_container_width=True):
                go_to_step(0)
                st.rerun()
        with col2:
            st.button("Add another account", icon=":material/add:", on_click=lambda: go_to_step(1),
                      use_container_width=True)


# Main Page Layout
st.title("Accounts Settings")
st.write("Here you can manage all the accounts that you have added to Spotidalyfin.")

# Spotify Section
display_subheader_with_icon("Spotify", "assets/ui/images/spotify_logo.svg", icon_position="right")
st.write("Here you can add or remove Spotify accounts.")

with st.container(border=True):
    st.write(
        "Here you can see all the Spotify accounts that you have added to Spotidalyfin."
        if get_authenticated_spotify_profiles() else
        "You haven't added any accounts yet."
    )

    for client_id, username in get_authenticated_spotify_profiles():

        col1, col2, col3 = create_aligned_columns([3, 4, 2])
        with col1:
            st.write(f"**{username}**")
        with col2:
            st.markdown(f"``{client_id}``")
        with col3:
            if st.button("Remove", key=username):
                st.info("This feature is not yet implemented.")

if st.button("Add Spotify account"):
    spotify_connection_dialog()

# TIDAL Section
display_subheader_with_icon("TIDAL", "assets/ui/images/tidal_logo.svg", icon_position="right")

st.write("Here you can add or remove TIDAL accounts.")
if st.button("Add TIDAL account"):
    st.info("This feature is not yet implemented.")
