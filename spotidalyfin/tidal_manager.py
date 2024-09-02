# tidal_manager.py
import random
import time
from pathlib import Path

from click.testing import CliRunner
from loguru import logger
from minim import tidal
from minim.tidal import API
from streamrip.rip import rip

from spotidalyfin.constants import DOWNLOAD_PATH
from spotidalyfin.utils import format_string


def get_tidal_client(client_id, client_secret):
    return tidal.API(client_id=client_id, client_secret=client_secret)


def search_tidal_track(client: API, track_name, artist_name, album_name, duration, retry_count=0):
    track_name, artist_name, album_name = map(format_string, [track_name, artist_name, album_name])

    try:
        results = client.search(f'{track_name} {artist_name}', "CH", type="TRACKS", limit=10)
    except Exception as e:
        if '429' in str(e) and retry_count < 5:  # 429 is a rate limit error
            backoff_time = (1.25 ** retry_count) + random.uniform(0, 0.3)  # Exponential backoff with jitter
            logger.debug(f"Rate limit hit, retrying in {backoff_time:.2f} seconds...")
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


def save_tidal_urls_to_file(tidal_urls: list, base_file_path: Path, split_count=3):
    # Split tidal URLs into three roughly equal parts
    split_urls = [tidal_urls[i::split_count] for i in range(split_count)]
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


# Used with tool "tidal-dl-ng" but replaced with tool "streamrip" for better performance
# def download_tracks_from_file(file_path: Path):
#     logger.info(f"Starting download from file: {file_path}")
#     try:
#         result = subprocess.run(["tidal-dl-ng", "dl", "-l", str(file_path)], check=True, capture_output=True, text=True)
#         # logger.info(result.stdout)
#         if result.stderr:
#             logger.warning(result.stderr)
#     except subprocess.CalledProcessError as e:
#         # Probable 429 error (rate limit)
#         if '429' in e.stderr:
#             logger.error(f"Download failed ({file_path.name}) with error 429. Retrying in 5 seconds...")
#             logger.warning(
#                 "You might be running too many workers at the same time. Try reducing the number of workers.")
#             time.sleep(5)
#             download_tracks_from_file(file_path)
#     except Exception as e:
#         logger.error(f"Unexpected error: {e}")
#     else:
#         logger.success(f"Download completed successfully ({file_path.name})")

def download_tracks_from_file(file_path: Path, retry_count=0):
    logger.info(f"Starting download from file: {file_path}")

    runner = CliRunner()
    result = runner.invoke(
        rip,
        [
            "--folder", DOWNLOAD_PATH,
            "--no-db",
            "--quality", "3",
            "--verbose",
            # "--no-progress",
            "file",
            str(file_path),
        ],
    )

    if "ERROR" in result.output:
        logger.warning("Error(s) occurred during download :")
        logger.warning(result.output)

    if result.exit_code != 0:
        if retry_count < 1:
            return download_tracks_from_file(file_path, retry_count + 1)
        else:
            raise Exception("Download failed.")


def process_and_download_tracks_concurrently(tidal_urls, workers=None):
    file_path = DOWNLOAD_PATH / "tidal_urls.txt"

    workers = 1
    # TODO : currently broken, metadata doesn't get written if workers > 1
    # if not workers:
    #     workers = min(4, len(tidal_urls))

    split_file_paths = save_tidal_urls_to_file(tidal_urls, file_path, workers)

    download_tracks_from_file(split_file_paths[0])

    # Run download processes concurrently using ProcessPoolExecutor
    # with ProcessPoolExecutor(max_workers=workers) as executor:
    #     futures = [executor.submit(download_tracks_from_file, file_path) for file_path in split_file_paths]
    #     for future in futures:
    #         try:
    #             future.result()  # Wait for the process to complete and catch any exceptions
    #         except Exception as e:
    #             logger.error(f"Error during download: {e}")
