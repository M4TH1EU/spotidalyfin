import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: Path):
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
            print(f"Error: Spotify ID {spotify_id} already exists in the database.")

    def put_many(self, matches: list[tuple[str, str]]):
        try:
            self.con.executemany("INSERT INTO matches(spotify_id, tidal_id) VALUES (?, ?)", matches)
            self.con.commit()
        except sqlite3.IntegrityError as e:
            print(f"Error: {e}")

    def get(self, spotify_id: str) -> str:
        cursor = self.con.execute("SELECT tidal_id FROM matches WHERE spotify_id = ?", (spotify_id,))
        match = cursor.fetchone()
        return match[0] if match else None
