# constants.py
from pathlib import Path

DOWNLOAD_PATH = Path("/home/mathieu/Téléchargements/notnoice")
FINAL_PATH = Path("/home/mathieu/Téléchargements/noice")
APPLICATION_PATH = Path(__file__).parent

# Credentials
SPOTIFY_CLIENT_ID = "ede847ad77904adead6ae2905f1b4e31"
SPOTIFY_CLIENT_SECRET = "c020905a91d441bb955040b813684261"

TIDAL_CLIENT_ID = "H3jekIIkCOpJfbwF"
TIDAL_CLIENT_SECRET = "4g20FCbN3bfqvMaHnZmdCi9hAwPVmKWJ3tZv1kO8mR4="

JELLYFIN_URL = "https://jellyfin.broillet.ch"
JELLYFIN_API_KEY = "945a0ad8f7de4654a5a5d44bce1e8257"

TIDAL_QUALITY = {
    "DOLBY_ATMOS": 0,
    "LOW": 1,
    "LOSSLESS": 2,
    "HIRES_LOSSLESS": 3,
    "HI_RES_LOSSLESS": 3
}
