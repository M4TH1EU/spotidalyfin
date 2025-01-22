import sqlite3
from pathlib import Path
from threading import Lock


class Database:

    def __init__(self, db_path: Path = Path("~/.config/spotidalyfin").expanduser() / "spotidalyfin.db",
                 reset: bool = False):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_lock = Lock()

        self.con = sqlite3.connect(self.db_path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row  # Access rows as dict-like objects

        if reset or not self.db_path.exists():
            self.initialize_database()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.con.rollback()
        self.con.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.db_lock:
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
        self.con.execute("DROP TABLE IF EXISTS matches;")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                spotify_id TEXT PRIMARY KEY,
                tidal_id TEXT NOT NULL
            );
        """)
        self.con.commit()
