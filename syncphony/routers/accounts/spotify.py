import re
from typing import Annotated
from urllib.parse import parse_qs, urlparse

import spotipy
from fastapi import APIRouter, HTTPException, Query, Depends
from spotipy import MemoryCacheHandler
from spotipy.oauth2 import SpotifyOAuth
from sqlmodel import Session

from syncphony.db.db import get_session
from syncphony.db.models import SpotifyAccount
from syncphony.storage.oauth_spotify import store_temp_oauth, get_temp_oauth, remove_temp_oauth

router = APIRouter()


@router.post("/spotify/start")
def start_spotify_auth(
        client_id: Annotated[str, Query(min_length=32, max_length=32)],
        client_secret: Annotated[str, Query(min_length=32, max_length=32)]
):
    # Create temporary OAuth object
    oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPES,
        cache_handler=MemoryCacheHandler(),  # do not store on disk
        open_browser=False
    )

    session_id = store_temp_oauth(oauth)
    auth_url = oauth.get_authorize_url()

    return {"auth_url": auth_url, "session_id": session_id}


@router.post("/spotify/finish")
def finish_spotify_auth(
        session_id: Annotated[str, Query(min_length=64, max_length=64)],
        redirect_uri: Annotated[str, Query()],
        db: Session = Depends(get_session)
):
    oauth = get_temp_oauth(session_id)
    if not oauth:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    query = urlparse(redirect_uri).query
    code = parse_qs(query).get("code", [None])[0]
    if not code:
        raise ValueError("Missing code param in redirect_uri")

    # Get the access token
    token_info = oauth.get_access_token(code=code, as_dict=True)
    if not token_info:
        raise HTTPException(status_code=400, detail="Failed to retrieve access token")

    user = spotipy.Spotify(oauth_manager=oauth).current_user()

    # Create or update the Spotify account in the database
    spotify_account = SpotifyAccount(
        username=user.get('id'),
        client_id=oauth.client_id,
        client_secret=oauth.client_secret,
        access_token=token_info['access_token'],
        expires_at=token_info['expires_at'],
        refresh_token=token_info.get('refresh_token', '')
    )

    db.add(spotify_account)
    db.commit()
    db.refresh(spotify_account)

    remove_temp_oauth(session_id)

    return {"message": "Spotify account linked successfully", "account": spotify_account}
