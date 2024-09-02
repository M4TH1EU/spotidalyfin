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

TIDAL_DL_NG_PATH = Path("~/.config/tidal_dl_ng/settings.json").expanduser()
TIDAL_DL_NG_CONFIG = {
    "skip_existing": "exact",
    "lyrics_embed": True,
    "lyrics_file": False,
    "video_download": False,
    "download_delay": False,
    "download_base_path": str(DOWNLOAD_PATH),
    "quality_audio": "HI_RES_LOSSLESS",
    "quality_video": "360",
    "format_album": "Albums/{album_artist} - {album_title}{album_explicit}/{album_track_num}. {artist_name} - {track_title}",
    "format_playlist": "Playlists/{playlist_name}/{artist_name} - {track_title}",
    "format_mix": "Mix/{mix_name}/{artist_name} - {track_title}",
    "format_track": "{artist_name} - {track_title}{track_explicit}",
    "format_video": "Videos/{artist_name} - {track_title}{track_explicit}",
    "video_convert_mp4": False,
    "path_binary_ffmpeg": "/usr/bin/ffmpeg",
    "metadata_cover_dimension": "320",
    "extract_flac": False,
    "downgrade_on_hi_res": False
}
