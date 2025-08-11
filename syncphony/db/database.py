import sqlite3
from pathlib import Path
from threading import Lock


class Database:

    def __init__(self, db_path: Path = Path("~/.config/syncphony").expanduser() / "syncphony.db",
                 reset: bool = False):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_lock = Lock()
        db_exists = self.db_path.exists()

        self.con = sqlite3.connect(self.db_path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row  # Access rows as dict-like objects

        if reset or not db_exists:
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

        self.con.execute("DROP TABLE IF EXISTS jellyfin_accounts;")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS jellyfin_accounts (
                url TEXT PRIMARY KEY,
                api TEXT NOT NULL
            );
        """)

        self.con.execute("DROP TABLE IF EXISTS subsonic_accounts;")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS subsonic_accounts (
                url TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                PRIMARY KEY (url, username)
            );
        """)

        self.con.execute("DROP TABLE IF EXISTS matches;")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                spotify_id TEXT,
                tidal_id TEXT,
                jellyfin_id TEXT,
                subsonic_id TEXT,
                PRIMARY KEY (spotify_id, tidal_id, jellyfin_id, subsonic_id)
            );
        """)

