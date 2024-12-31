import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: Path = Path("~/.config/spotidalyfin").expanduser() / "spotidalyfin.db"):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.db_path)
        self.initialize_database()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.con.close()

    def initialize_database(self):
        self.con.execute("DROP TABLE IF EXISTS spotify_accounts;")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS spotify_accounts (
                client_id TEXT,
                client_secret TEXT,
                username TEXT,
                data TEXT
            );
        """)
        self.con.commit()

if __name__ == '__main__':
    with Database() as db:
        db.initialize_database()