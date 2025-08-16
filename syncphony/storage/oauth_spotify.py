from spotipy.oauth2 import SpotifyOAuth
from typing import Dict
from uuid import uuid4

TEMP_OAUTH_STORE: Dict[str, SpotifyOAuth] = {}

def store_temp_oauth(oauth: SpotifyOAuth) -> str:
    session_id = str(uuid4())
    TEMP_OAUTH_STORE[session_id] = oauth
    return session_id

def get_temp_oauth(session_id: str) -> SpotifyOAuth:
    return TEMP_OAUTH_STORE.get(session_id)

def remove_temp_oauth(session_id: str):
    TEMP_OAUTH_STORE.pop(session_id, None)