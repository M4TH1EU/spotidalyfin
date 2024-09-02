import sqlite3
from contextlib import contextmanager
from pathlib import Path

from spotidalyfin import constants

DB_FILE = constants.FINAL_PATH / "spotidalyfin.db"


@contextmanager
def get_connection():
    """Context manager to handle database connections."""
    db_path = Path(DB_FILE)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        yield con
    finally:
        con.close()


def initialize_database():
    """Initialize the database with the required table."""
    with get_connection() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                spotify_id TEXT PRIMARY KEY,
                tidal_id TEXT
            )
        """)
        con.commit()


def put(spotify_id: str, tidal_id: str):
    """Insert a new match into the database."""
    try:
        with get_connection() as con:
            con.execute("INSERT INTO matches(spotify_id, tidal_id) VALUES (?, ?)", (spotify_id, tidal_id))
            con.commit()
    except sqlite3.IntegrityError:
        print(f"Error: Spotify ID {spotify_id} already exists in the database.")


def put_many(matches: list[tuple[str, str]]):
    """Insert multiple matches into the database."""
    try:
        with get_connection() as con:
            con.executemany("INSERT INTO matches(spotify_id, tidal_id) VALUES (?, ?)", matches)
            con.commit()
    except sqlite3.IntegrityError as e:
        print(f"Error: {e}")


def get(spotify_id: str) -> str:
    """Retrieve a Tidal ID using a Spotify ID."""
    with get_connection() as con:
        cursor = con.execute("SELECT tidal_id FROM matches WHERE spotify_id = ?", (spotify_id,))
        match = cursor.fetchone()
        return match[0] if match else None
