# constants.py
import sys
from pathlib import Path

DEBUG = False

DOWNLOAD_PATH = Path("/tmp/spotidalyfin")
FINAL_PATH = Path("~/Music/spotidalyfin").expanduser()
APPLICATION_PATH = Path(
    sys._MEIPASS if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS') else __file__).resolve().parent

# Credentials
SPOTIFY_CLIENT_ID = ""
SPOTIFY_CLIENT_SECRET = ""

TIDAL_CLIENT_ID = ""
TIDAL_CLIENT_SECRET = "="

JELLYFIN_URL = ""
JELLYFIN_API_KEY = ""

TIDAL_QUALITY = {
    "DOLBY_ATMOS": 0,
    "LOW": 1,
    "LOSSLESS": 2,
    "HIRES_LOSSLESS": 3,
    "HI_RES_LOSSLESS": 3
}
