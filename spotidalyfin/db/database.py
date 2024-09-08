import sqlite3
from pathlib import Path
from typing import Optional

from tidalapi import Track

from spotidalyfin import cfg
from spotidalyfin.managers.tidal_manager import TidalManager
from spotidalyfin.utils.logger import log


class Database:
    def __init__(self, db_path: Path = cfg.get("config-dir") / "spotidalyfin.db"):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.db_path)
        self.initialize_database()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.con.close()

    def initialize_database(self):
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                spotify_id TEXT PRIMARY KEY,
                tidal_id TEXT
            )
        """)
        self.con.commit()

    def put(self, spotify_id: str, tidal_id: str):
        try:
            self.con.execute("INSERT INTO matches(spotify_id, tidal_id) VALUES (?, ?)", (spotify_id, tidal_id))
            self.con.commit()
        except sqlite3.IntegrityError:
            # Already exists
            self.remove(spotify_id)
            self.put(spotify_id, tidal_id)

    def put_many(self, matches: list[tuple[str, str]]):
        try:
            self.con.executemany("INSERT INTO matches(spotify_id, tidal_id) VALUES (?, ?)", matches)
            self.con.commit()
        except sqlite3.IntegrityError as e:
            log.error(f"Error: {e}")

    def get(self, spotify_id: str) -> str:
        cursor = self.con.execute("SELECT tidal_id FROM matches WHERE spotify_id = ?", (spotify_id,))
        match = cursor.fetchone()
        return match[0] if match else None

    def remove(self, spotify_id: str):
        try:
            self.con.execute("DELETE FROM matches WHERE spotify_id = ?", (spotify_id,))
            self.con.commit()
        except sqlite3.IntegrityError as e:
            log.error(f"Error: {e}")

    def get_tidal_track_from_database(self, spotify_id: str, tidal_manager: TidalManager) -> Optional[Track]:
        tidal_id = self.get(spotify_id)
        if tidal_id:
            track = tidal_manager.get_track(tidal_id)
            if track:
                return track
        return None
