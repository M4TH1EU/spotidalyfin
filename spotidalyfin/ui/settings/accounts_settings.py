from typing import List

import streamlit as st

from spotidalyfin.db.helpers import get_authenticated_spotify_profiles, remove_spotify_profile, remove_tidal_profile, \
    get_authenticated_tidal_profiles
from spotidalyfin.managers.spotify_manager import create_temporary_oauth, try_to_authenticate_with_spotify
from spotidalyfin.managers.tidal_manager import try_to_authenticate_with_tidal, create_temporary_session
from spotidalyfin.ui.helpers.dialogs import DialogContext, DialogStep, MultiStepDialog
from spotidalyfin.ui.helpers.getters import get_database
from spotidalyfin.ui.helpers.ui import subheader_custom_icon, display_table


# Callback to update the current step
def go_to_step(step):
    """Update the current step."""
    st.session_state.spot_dialog["step"] = step


def create_and_add_spotify_dialog():
    def step1_content(context: DialogContext):
        """Step 1: Collect Spotify App credentials"""
        st.info("Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications) "
                "to create a new Spotify application if needed.")
        st.warning("Set the Redirect URI to : `http://127.0.0.1:6969`")

        client_id = st.text_input("Client ID", value=context.get("client_id", ""))
        client_secret = st.text_input("Client Secret", value=context.get("client_secret", ""), type="password")

        # Store values in context
        context.set("client_id", client_id)
        context.set("client_secret", client_secret)

    def validate_step1(context: DialogContext) -> tuple[bool, str]:
        """Validate Spotify credentials"""
        if not all([context.get("client_id"), context.get("client_secret")]):
            return False, "Please fill in all fields to continue."

        if len(context.get("client_id")) != 32:
            return False, "Invalid Client ID. Please check the Client ID and try again."
        if len(context.get("client_secret")) != 32:
            return False, "Invalid Client Secret. Please check the Client Secret and try again."

        # Create a temporary OAuth object to check if the credentials are valid
        spotify_dialog.get_context().set("oauth",
                                         create_temporary_oauth(context.get("client_id"), context.get("client_secret")))

        return True, ""

    def step2_content(context: DialogContext):
        """Step 2: Authorization URL and code"""
        st.info(
            "Visit the following URL to authorize Spotidalyfin to access your Spotify account.  \n**You will be redirected to an invalid URL, copy and paste it below.**")

        st.markdown(f"[Authorize Spotify]({context.get("oauth").get_authorize_url()})", unsafe_allow_html=True)

        # Get redirect URL
        redirect_url = st.text_input("Enter the URL you were redirected to after authorization.")
        context.set("redirect_url", redirect_url)

    def validate_step2(context: DialogContext) -> tuple[bool, str]:
        """Validate authorization"""
        if not context.get("redirect_url"):
            return False, "Please enter the URL you were redirected to after authorizing Spotidalyfin."

        return try_to_authenticate_with_spotify(context.get("oauth"), context.get("redirect_url"), get_database())

    def step3_content(context: DialogContext):
        """Step 3: Completion"""
        st.success("Your Spotify account has been successfully connected.")

        # Clear sensitive data
        # TODO: do that in dialog class not here
        context.set("client_id", "")
        context.set("client_secret", "")
        context.set("redirect_url", "")
        context.set("oauth", None)


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
    profiles = get_authenticated_spotify_profiles(get_database())

    if profiles:
        # Prepare data for display_table
        data: List[List] = [
            ["Username", "Actions"]  # Header row
        ]

        for username in profiles:
            data.append([
                f"`{username}`",  # Display username in bold
                lambda u=username: st.button("Remove", key=u, on_click=remove_spotify_profile,
                                             args=(get_database(), u,))  # Remove button (attention late-binding)
            ])

        # Call display_table to render
        display_table(
            data=data,
            columns=[3, 2],  # Aligned column widths
            text="Here you can see all the Spotify accounts that you have added to Spotidalyfin.",
            border=True,
            header=True,
            align="left",
            gap="small",
            vertical_alignment="center"
        )
    else:
        # No profiles available
        st.write("*You haven't added any accounts yet.*")


def create_and_add_tidal_dialog():
    def step1_content(context: DialogContext):
        """Step 1: Authorization URL"""
        st.info(
            "Visit the following URL to authorize Spotidalyfin to access your TIDAL account.  \n**You will be redirected to an invalid URL, copy and paste it below.**")

        st.markdown(f"[Authorize TIDAL]({context.get("session").pkce_login_url()})", unsafe_allow_html=True)

        # Get redirect URL
        redirect_url = st.text_input("Enter the URL you were redirected to after authorization.")
        context.set("redirect_url", redirect_url)

    def validate_step1(context: DialogContext) -> tuple[bool, str]:
        """Validate authorization"""
        if not context.get("redirect_url"):
            return False, "Please enter the URL you were redirected to after authorizing Spotidalyfin."

        # this tries to authenticate, checks if the account is already authenticated and saves it to the database if not
        return try_to_authenticate_with_tidal(context.get("session"), context.get("redirect_url"), get_database())

    def step2_content(context: DialogContext):
        """Step 2: Completion"""
        st.success("Your TIDAL account has been successfully connected.")

        # Clear sensitive data
        context.set("redirect_url", "")  # TODO: do that in dialog class not here

    # Create the dialog steps
    step1 = DialogStep(
        title="Step 1: Authorize Spotidalyfin",
        content=step1_content,
        validation_func=validate_step1,
        next_button_text="Connect"
    )

    step2 = DialogStep(
        title="Step 2: Setup Complete!",
        content=step2_content,
        next_button_text="Close"
    )

    # Create the dialog
    tidal_dialog = MultiStepDialog(
        name="TIDAL Connection",
        steps=[step1, step2],
        show_progress_bar=True,
    )

    # Show the dialog
    if st.button("Connect TIDAL Account"):
        tidal_dialog.get_context().set("session", create_temporary_session())
        tidal_dialog.render()


def tidal_accounts_table():
    # Check if there are authenticated TIDAL profiles
    profiles = get_authenticated_tidal_profiles(get_database())

    if profiles:
        # Prepare data for display_table
        data: List[List] = [
            ["Username", "Actions"]  # Header row
        ]

        for username in profiles:
            data.append([
                f"`{username}`",  # Display username in bold
                lambda u=username: st.button("Remove", key=u, on_click=remove_tidal_profile,
                                             args=(get_database(), u,))  # Remove button (attention late-binding)
            ])

        # Call display_table to render
        display_table(
            data=data,
            columns=[3, 2],  # Aligned column widths
            text="Here you can see all the TIDAL accounts that you have added to Spotidalyfin.",
            border=True,
            header=True,
            align="left",
            gap="small",
            vertical_alignment="center"
        )
    else:
        # No profiles available
        st.write("*You haven't added any accounts yet.*")


# Main Page Layout
st.title("Accounts Settings")
st.write("Here you can manage all the accounts that you have added to Spotidalyfin.")

# Spotify Section
subheader_custom_icon("Spotify", "assets/ui/images/spotify_logo.svg", icon_position="right")
st.write("Here you can add or remove Spotify accounts.")

spotify_accounts_table()
create_and_add_spotify_dialog()

# TIDAL Section
subheader_custom_icon("TIDAL", "assets/ui/images/tidal_logo.svg", icon_position="right")
st.write("Here you can add or remove TIDAL accounts.")

tidal_accounts_table()
create_and_add_tidal_dialog()
