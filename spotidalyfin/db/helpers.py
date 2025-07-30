import sqlite3
from typing import List, Optional

from spotipy import CacheHandler, SpotifyOAuth

from spotidalyfin import SPOTIFY_SCOPES, SPOTIFY_REDIRECT_URI
from spotidalyfin.db.database import Database
from spotidalyfin.utils.logger import log


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
            (self.username,)
        )
        token_info = cursor.fetchone()
        if token_info:
            return {
                "access_token": token_info[0],
                "token_type": "Bearer",
                # "expires_in": 0,
                "expires_at": token_info[1],
                "refresh_token": token_info[2],
                "scope": " ".join(SPOTIFY_SCOPES)
            }

        return {}

    def save_token_to_cache(self, token_info) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO spotify_accounts (username, client_id, client_secret, access_token, expires_at, refresh_token) VALUES (?, ?, ?, ?, ?, ?)",
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
    client_id, client_secret = cursor.fetchone()

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


def get_tidal_login_info(db: Database, username: str) -> tuple[str, str]:
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


def get_authenticated_jellyfin_profiles(db: Database) -> List[str]:
    """Get the authenticated Jellyfin profiles."""
    res = db.execute("SELECT url FROM jellyfin_accounts").fetchall()
    return [r[0] for r in res]


def remove_jellyfin_profile(db: Database, url: str) -> None:
    """Remove a Jellyfin profile from the database."""
    db.execute("DELETE FROM jellyfin_accounts WHERE url=?", (url,))
    db.commit()


def save_jellyfin_info_to_db(db: Database, url: str, api_key: str) -> None:
    """Save Jellyfin login information to the database."""
    db.execute(
        "INSERT INTO jellyfin_accounts (url, api) VALUES (?, ?)",
        (url, api_key)
    )
    db.commit()


def get_jellyfin_api_key(db: Database, url: str) -> Optional[str]:
    """Get the Jellyfin API key for the given URL."""
    cursor = db.execute("SELECT api FROM jellyfin_accounts WHERE url=?", (url,))
    res = cursor.fetchone()
    return res[0] if res else None


def get_authenticated_subsonic_profiles(db: Database) -> List[tuple[str]]:
    """Get the authenticated Subsonic profiles."""
    res = db.execute("SELECT url, username FROM subsonic_accounts").fetchall()
    return [tuple(r) for r in res]

def get_subsonic_login_password(db: Database, url: str, username: str) -> Optional[str]:
    """Get the Subsonic login password for the given URL and username."""
    cursor = db.execute("SELECT password FROM subsonic_accounts WHERE url=? AND username=?", (url, username))
    res = cursor.fetchone()
    return res[0] if res else None

def remove_subsonic_profile(db: Database, url: str, username: str) -> None:
    """Remove a Subsonic profile from the database."""
    db.execute("DELETE FROM subsonic_accounts WHERE url=? AND username=?", (url, username))
    db.commit()

def save_subsonic_info_to_db(db: Database, url: str, username: str, password: str) -> None:
    """Save Subsonic login information to the database."""
    db.execute(
        "INSERT INTO subsonic_accounts (url, username, password) VALUES (?, ?, ?)",
        (url, username, password)
    )
    db.commit()


def get_tidal_track_id_from_spotify_id(db: Database, spotify_id: str) -> Optional[str]:
    """Get the TIDAL track ID from the Spotify track ID."""
    if not spotify_id:
        log.error(
            "Error while retrieving TIDAL track ID from Spotify ID: spotify_id must be a non-empty string: " + str(
                spotify_id))
        return None

    try:
        cursor = db.execute("SELECT tidal_id FROM matches WHERE spotify_id=?", (str(spotify_id),))
        res = cursor.fetchone()
        return str(res[0]) if res else None
    except sqlite3.InterfaceError as e:
        log.error(f"SQLite InterfaceError: {e}, Parameters: {spotify_id}")
    except Exception as e:
        log.error(f"Unexpected error while retrieving TIDAL track ID from Spotify ID: {e}")

    return None


def save_match(db: Database, spotify_id: str, tidal_id: str) -> None:
    """Save a match between a Spotify and TIDAL track."""
    if not spotify_id or not tidal_id:
        log.error(f"Error while saving match: spotify_id and tidal_id must be non-empty strings: "
                  f"{spotify_id}, {tidal_id}")
        return

    try:
        db.execute(
            """
            INSERT OR REPLACE INTO matches (spotify_id, tidal_id)
            VALUES (?, ?)
            """,
            (str(spotify_id), str(tidal_id)),
        )
        db.commit()
    except sqlite3.InterfaceError as e:
        log.error(f"SQLite InterfaceError: {e}, Parameters: {spotify_id}, {tidal_id}")
    except Exception as e:
        log.error(f"Unexpected error while saving match: {e}")
