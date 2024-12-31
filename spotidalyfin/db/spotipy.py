import json

from spotipy import CacheHandler

from spotidalyfin.db.database import Database


class SpotidalyfinSpotifyDatabaseCache(CacheHandler):
    """
    Handles reading and writing cached Spotify authorization tokens
    in the Spotidalyfin database.
    """

    def __init__(self, db: Database, client_id: str, client_secret: str, username: str):
        self.db = db
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username

    def get_cached_token(self):
        with self.db as db:
            cursor = db.con.execute(
                "SELECT data FROM spotify_accounts WHERE client_id = ? AND client_secret = ? AND username = ?",
                (self.client_id, self.client_secret, self.username)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def save_token_to_cache(self, token_info):
        with self.db as db:
            db.con.execute(
                "INSERT OR REPLACE INTO spotify_accounts (client_id, client_secret, username, data) VALUES (?, ?, ?, ?)",
                (self.client_id, self.client_secret, self.username, json.dumps(token_info))
            )
            db.con.commit()