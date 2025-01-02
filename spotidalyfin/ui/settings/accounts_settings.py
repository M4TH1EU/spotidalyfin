from typing import List

import streamlit as st

from spotidalyfin.ui.helpers.database import get_authenticated_spotify_profiles, remove_spotify_profile
from spotidalyfin.ui.helpers.dialogs import DialogContext, DialogStep, MultiStepDialog
from spotidalyfin.ui.helpers.spotify import get_spotify_manager
from spotidalyfin.ui.helpers.ui import display_subheader_with_icon, display_table


# Callback to update the current step
def go_to_step(step):
    """Update the current step."""
    st.session_state.spot_dialog["step"] = step


def create_and_add_spotify_dialog():
    def step1_content(context: DialogContext):
        """Step 1: Collect Spotify App credentials"""
        st.info("Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications) "
                "to create a new Spotify application if needed.")

        client_id = st.text_input("Client ID", value=context.get("client_id", ""))
        client_secret = st.text_input("Client Secret", value=context.get("client_secret", ""), type="password")
        spotify_username = st.text_input("Spotify Username", value=context.get("spotify_username", ""))

        # Store values in context
        context.set("client_id", client_id)
        context.set("client_secret", client_secret)
        context.set("spotify_username", spotify_username)

    def validate_step1(context: DialogContext) -> tuple[bool, str]:
        """Validate Spotify credentials"""
        if not all([context.get("client_id"), context.get("client_secret"), context.get("spotify_username")]):
            return False, "Please fill in all fields to continue."

        if len(context.get("client_id")) != 32:
            return False, "Invalid Client ID. Please check the Client ID and try again."
        if len(context.get("client_secret")) != 32:
            return False, "Invalid Client Secret. Please check the Client Secret and try again."

        if context.get("spotify_username") in [x[1] for x in get_authenticated_spotify_profiles()]:
            return False, "This account is already authenticated."

        return True, ""

    def step2_content(context: DialogContext):
        """Step 2: Authorization URL and code"""
        st.info(
            "Visit the following URL to authorize Spotidalyfin to access your Spotify account.  \n**You will be redirected to an invalid URL, copy and paste it below.**")
        # Generate authorization URL
        auth_url = get_spotify_manager(
            context.get("client_id"),
            context.get("client_secret"),
            context.get("spotify_username")
        ).authorize_url

        st.markdown(f"[Authorize Spotify]({auth_url})", unsafe_allow_html=True)

        # Get redirect URL
        redirect_url = st.text_input("Enter the URL you were redirected to after authorization.")
        context.set("redirect_url", redirect_url)

    def validate_step2(context: DialogContext) -> tuple[bool, str]:
        """Validate authorization"""
        if not context.get("redirect_url"):
            return False, "Please enter the URL you were redirected to after authorizing Spotidalyfin."

        success = get_spotify_manager(
            context.get("client_id"),
            context.get("client_secret"),
            context.get("spotify_username")
        ).authenticate(context.get("redirect_url"))

        if not success:
            return False, "Failed to connect. Please check your authorization code."

        return True, ""

    def step3_content(context: DialogContext):
        """Step 3: Completion"""
        st.success("Your Spotify account has been successfully connected.")

        # Clear sensitive data
        context.set("client_id", "")
        context.set("client_secret", "")
        context.set("spotify_username", "")
        context.set("redirect_url", "")

    # Create the dialog steps
    step1 = DialogStep(
        title="Step 1: Provide Spotify App Details",
        content=step1_content,
        validation_func=validate_step1,
        next_button_text="Next"
    )

    step2 = DialogStep(
        title="Step 2: Authorize Spotidalyfin",
        content=step2_content,
        validation_func=validate_step2,
        next_button_text="Connect"
    )

    step3 = DialogStep(
        title="Step 3: Setup Complete!",
        content=step3_content,
        next_button_text="Close"
    )

    # Create the dialog
    spotify_dialog = MultiStepDialog(
        name="Spotify Connection",
        steps=[step1, step2, step3],
        show_progress_bar=True,
    )

    # Show the dialog
    if st.button("Connect Spotify Account"):
        spotify_dialog.render()


def spotify_accounts_table():
    # Check if there are authenticated Spotify profiles
    profiles = get_authenticated_spotify_profiles()

    if profiles:
        # Prepare data for display_table
        data: List[List] = [
            ["Username", "Client ID", "Actions"]  # Header row
        ]

        for client_id, username in profiles:
            data.append([
                f"**{username}**",  # Display username in bold
                f"`{client_id}`",  # Display client ID as inline code
                lambda u=username: st.button("Remove", key=u, on_click=remove_spotify_profile, args=(u,))
                # Remove button (attention late-binding)
            ])

        # Call display_table to render
        display_table(
            data=data,
            columns=[3, 4, 2],  # Aligned column widths
            text="Here you can see all the Spotify accounts that you have added to Spotidalyfin.",
            border=True,
            header=True,
            align="left",
            gap="small",
            vertical_alignment="center"
        )
    else:
        # No profiles available
        st.write("You haven't added any accounts yet.")


# Main Page Layout
st.title("Accounts Settings")
st.write("Here you can manage all the accounts that you have added to Spotidalyfin.")

# Spotify Section
display_subheader_with_icon("Spotify", "assets/ui/images/spotify_logo.svg", icon_position="right")
st.write("Here you can add or remove Spotify accounts.")

spotify_accounts_table()

# with st.container(border=True):
#     st.write(
#         "Here you can see all the Spotify accounts that you have added to Spotidalyfin."
#         if get_authenticated_spotify_profiles() else
#         "You haven't added any accounts yet."
#     )
#
#     for client_id, username in get_authenticated_spotify_profiles():
#
#         col1, col2, col3 = create_aligned_columns([3, 4, 2])
#         with col1:
#             st.write(f"**{username}**")
#         with col2:
#             st.markdown(f"``{client_id}``")
#         with col3:
#             if st.button("Remove", key=username):
#                 st.info("This feature is not yet implemented.")

create_and_add_spotify_dialog()

# TIDAL Section
display_subheader_with_icon("TIDAL", "assets/ui/images/tidal_logo.svg", icon_position="right")

st.write("Here you can add or remove TIDAL accounts.")
if st.button("Add TIDAL account"):
    st.info("This feature is not yet implemented.")
