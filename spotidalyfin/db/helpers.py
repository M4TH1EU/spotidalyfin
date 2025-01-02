from typing import List

from spotipy import CacheHandler, SpotifyOAuth

from spotidalyfin import SPOTIFY_SCOPES, SPOTIFY_REDIRECT_URI
from spotidalyfin.db.database import Database


class SpotipyCacheDatabaseHandler(CacheHandler):
    """
    Handles reading and writing cached Spotify authorization tokens
    in the Spotidalyfin database.
    """

    def __init__(self, db: Database, client_id: str, client_secret: str, username: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.db = db

    def get_cached_token(self) -> dict:
        cursor = self.db.execute(
            "SELECT access_token, expires_at, refresh_token FROM spotify_accounts WHERE username=?",
        )
        token_info = cursor.fetchone()
        if token_info:
            return {
                "access_token": token_info[0],
                "token_type": "Bearer",
                # "expires_in": 0,
                "expires_at": token_info[1],
                "refresh_token": token_info[2],
                "scope": SPOTIFY_SCOPES
            }

        return {}

    def save_token_to_cache(self, token_info) -> None:
        self.db.execute(
            "INSERT INTO spotify_accounts (username, client_id, client_secret, access_token, expires_at, refresh_token) VALUES (?, ?, ?, ?, ?, ?)",
            (self.username, self.client_id, self.client_secret, token_info["access_token"], token_info["expires_at"],
             token_info["refresh_token"])
        )
        self.db.commit()


def save_spotify_into_db(db: Database, username: str, oauth: SpotifyOAuth) -> None:
    """Save Spotify login information to the database."""
    db.execute(
        "INSERT INTO spotify_accounts (username, client_id, client_secret, access_token, expires_at, refresh_token) VALUES (?, ?, ?, ?, ?, ?)",
        (username, oauth.client_id, oauth.client_secret, oauth.get_cached_token()["access_token"],
         oauth.get_cached_token()["expires_at"], oauth.get_cached_token()["refresh_token"])
    )
    db.commit()


def get_spotify_oauth(db: Database, username: str) -> SpotifyOAuth:
    """Get the SpotifyOAuth object for the given username."""
    cursor = db.execute(
        "SELECT client_id, client_secret FROM spotify_accounts WHERE username=?", (username,)
    )
    client_id, client_secret = cursor
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPES,
        cache_handler=SpotipyCacheDatabaseHandler(db, client_id, client_secret, username),
        open_browser=False
    )


def get_authenticated_spotify_profiles(db: Database) -> List[str]:
    """Get the authenticated Spotify profiles."""
    res = db.execute("SELECT username FROM spotify_accounts").fetchall()
    return [r[0] for r in res]


def remove_spotify_profile(db: Database, username: str) -> None:
    """Remove a Spotify profile from the database."""
    db.execute("DELETE FROM spotify_accounts WHERE username=?", (username,))
    db.commit()


def save_tidal_info_to_db(db: Database, login_info: dict) -> None:
    """Save TIDAL login information to the database."""
    db.execute(
        "INSERT INTO tidal_accounts (username, access_token, refresh_token) VALUES (?, ?, ?)",
        (login_info["user"]["username"], login_info["access_token"], login_info["refresh_token"])
    )
    db.commit()


def get_tidal_login_info(db: Database, username: str) -> dict:
    """Get the TIDAL login information for the given username."""
    cursor = db.execute("SELECT access_token, refresh_token FROM tidal_accounts WHERE username=?", (username,))
    return cursor.fetchone()


def get_authenticated_tidal_profiles(db: Database) -> List[str]:
    """Get the authenticated TIDAL profiles."""
    res = db.execute("SELECT username FROM tidal_accounts").fetchall()
    return [r[0] for r in res]


def remove_tidal_profile(db: Database, username: str) -> None:
    """Remove a TIDAL profile from the database."""
    db.execute("DELETE FROM tidal_accounts WHERE username=?", (username,))
    db.commit()
