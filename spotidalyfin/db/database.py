import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: Path = Path("~/.config/spotidalyfin").expanduser() / "spotidalyfin.db",
                 reset: bool = False):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.con = sqlite3.connect(self.db_path, check_same_thread=False)

        if reset or not self.db_path.exists():
            self.initialize_database()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.con.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.con.execute(query, params)

    def commit(self) -> None:
        self.con.commit()

    def initialize_database(self):
        self.con.execute("DROP TABLE IF EXISTS spotify_accounts;")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS spotify_accounts (
                username TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                client_secret TEXT NOT NULL,
                access_token TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                refresh_token TEXT NOT NULL
            );
        """)
        self.con.execute("DROP TABLE IF EXISTS tidal_accounts;")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS tidal_accounts (
                username TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL
            );
        """)
        self.con.commit()
