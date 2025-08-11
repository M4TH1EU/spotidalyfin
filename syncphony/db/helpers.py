from typing import List
from typing import Optional

from spotipy import CacheHandler, SpotifyOAuth

from syncphony import SPOTIFY_SCOPES, SPOTIFY_REDIRECT_URI
from syncphony.db.database import Database
from syncphony.models.enums import Platform


class SpotipyCacheDatabaseHandler(CacheHandler):
    """
    Handles reading and writing cached Spotify authorization tokens
    in the Syncphony database.
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


def get_match_for_itemid_from_db(db: Database, item_id: str, src_platform: Platform, dest_platform: Platform) -> \
        Optional[str]:
    """Search the database for a match of the given ID on the destination platform."""
    cursor = db.execute(
        f"SELECT {f"{dest_platform.value.lower()}_id"} FROM matches WHERE {f"{src_platform.value.lower()}_id"} = ?",
        (item_id,)
    )
    res = cursor.fetchone()
    return res[0] if res and res[0] else None


def save_match_to_db(
        db: Database,
        src_id: str,
        src_platform: Platform,
        dest_id: str,
        dest_platform: Platform
) -> None:
    """Save a match between two platforms in the database."""

    # Explicitly tell type checker: dict[str, Optional[str]]
    columns: dict[str, Optional[str]] = {f"{p.value.lower()}_id": None for p in Platform}

    # Fill in source and destination IDs
    columns[f"{src_platform.value.lower()}_id"] = src_id
    columns[f"{dest_platform.value.lower()}_id"] = dest_id

    # Build the SQL dynamically
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"""
        INSERT OR REPLACE INTO matches ({", ".join(columns)})
        VALUES ({placeholders})
    """

    db.execute(sql, tuple(columns.values()))
    db.commit()
