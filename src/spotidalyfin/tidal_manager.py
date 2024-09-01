# tidal_manager.py
import random
import subprocess
import time
from pathlib import Path

from loguru import logger
from minim import tidal

from utils import format_string


def get_tidal_client(client_id, client_secret):
    return tidal.API(client_id=client_id, client_secret=client_secret)

def search_tidal_track(client, track_name, artist_name, album_name, duration, retry_count=0):
    track_name, artist_name, album_name = map(format_string, [track_name, artist_name, album_name])

    try:
        results = client.search(f'{track_name} {artist_name}', "CH", type="TRACKS", limit=15)
    except Exception as e:
        if '429' in str(e) and retry_count < 5:  # 429 is a rate limit error
            backoff_time = (2 ** retry_count) + random.uniform(0, 1)  # Exponential backoff with jitter
            logger.warning(f"Rate limit hit, retrying in {backoff_time:.2f} seconds...")
            time.sleep(backoff_time)
            return search_tidal_track(client, track_name, artist_name, album_name, duration, retry_count + 1)
        else:
            logger.error(f"Failed to search track: {e}")
            return None

    for track in results['tracks']:
        tidal_track = track['resource']
        if (
                format_string(tidal_track['title']) == track_name and
                format_string(tidal_track['artists'][0]['name']) == artist_name and
                abs(duration - tidal_track['duration']) < 3
        ):
            return tidal_track['id']

    return None


def save_tidal_urls_to_file(tidal_urls: list, base_file_path: Path):
    # Split tidal URLs into three roughly equal parts
    split_urls = [tidal_urls[i::3] for i in range(3)]
    file_paths = []

    for i, urls in enumerate(split_urls):
        file_path = base_file_path.with_name(f"{base_file_path.stem}_part_{i + 1}{base_file_path.suffix}")
        file_paths.append(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            for url in urls:
                f.write(f"https://tidal.com/browse/track/{url}\n")
        logger.info(f"Saved Tidal URLs to {file_path}")

    return file_paths


# def download_tracks_from_file(file_path):
#     logger.info(f"Starting download from file: {file_path}")
#     sys.argv = ["tidal-dl-ng", "dl", "-l", str(file_path)]
#     try:
#         tidal_dl_ng.app()
#     except SystemExit as e:
#         if e.code != 0:
#             logger.error(f"Download failed with error code: {e.code}")
#     except Exception as e:
#         logger.error(f"Unexpected error: {e}")
#     else:
#         logger.success("Download completed successfully!")

def download_tracks_from_file(file_path: Path):
    logger.info(f"Starting download from file: {file_path}")
    try:
        result = subprocess.run(["tidal-dl-ng", "dl", "-l", str(file_path)], check=True, capture_output=True, text=True)
        # logger.info(result.stdout)
        if result.stderr:
            logger.warning(result.stderr)
    except subprocess.CalledProcessError as e:
        logger.error(f"Download failed with error: {e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    else:
        logger.success("Download completed successfully!")

# def download_track_from_tidal(track_id: str):
#     download_tracks_from_file(track_id)
