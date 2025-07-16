import sys
from pathlib import Path

APPLICATION_PATH = Path(sys._MEIPASS).resolve() if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS') else Path(
    __file__).resolve().parent

SPOTIFY_SCOPES = ['playlist-read-private', 'playlist-read-collaborative', 'user-library-read', 'playlist-modify-public', 'playlist-modify-private']
SPOTIFY_REDIRECT_URI = 'http://127.0.0.1:6969'
