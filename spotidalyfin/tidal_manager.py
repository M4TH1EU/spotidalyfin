# tidal_manager.py

import random
import tempfile
import time
import uuid
from pathlib import Path

from click.testing import CliRunner
from loguru import logger
from minim import tidal
from minim.tidal import API
from streamrip.rip import rip

from spotidalyfin import tidal_matcher
from spotidalyfin.constants import DOWNLOAD_PATH


def get_tidal_client(client_id: str, client_secret: str) -> API:
    """
    Initialize and return a Tidal API client using provided credentials.
    """
    return tidal.API(client_id=client_id, client_secret=client_secret)


def search_tidal_track(client: API, spotify_track: dict, retry_count: int = 0, fast_search: bool = False) -> str:
    """
    Search for a Tidal track matching the given Spotify track.

    Args:
        client (API): Tidal API client.
        spotify_track (dict): Spotify track details.
        retry_count (int): Number of retries in case of rate limiting.
        fast_search (bool): Whether to perform a fast search (default: False).

    Returns:
        str: Tidal track ID if a match is found, otherwise None.
    """
    try:
        if fast_search:
            matches = tidal_matcher.search_for_track(client, spotify_track)
        else:
            matches = tidal_matcher.search_for_track_in_album(client, spotify_track)
            if not matches:
                matches = tidal_matcher.search_for_track(client, spotify_track)

        if matches:
            best_track = tidal_matcher.get_best_quality_track(matches)
            return best_track.get('id')

    except Exception as e:
        if '429' in str(e) and retry_count < 7:  # 429 indicates a rate limit error
            backoff_time = (1.5 ** retry_count) + random.uniform(0.3, 0.7)  # Exponential backoff with jitter
            logger.debug(f"Rate limit hit, retrying in {backoff_time:.2f} seconds...")
            time.sleep(backoff_time)
            return search_tidal_track(client, spotify_track, retry_count + 1)
        else:
            logger.error(f"Failed to search for track: {e}")

    return ""


def save_tidal_urls_to_file(tidal_urls: list, base_file_path: Path, split_count: int = 3) -> list:
    """
    Split Tidal URLs into multiple files and save them.

    Args:
        tidal_urls (list): List of Tidal track URLs.
        base_file_path (Path): Base file path for saving URLs.
        split_count (int): Number of parts to split the URLs into.

    Returns:
        list: List of file paths where URLs are saved.
    """
    split_urls = [tidal_urls[i::split_count] for i in range(split_count)]
    file_paths = []

    for i, urls in enumerate(split_urls):
        split_file_path = base_file_path.with_name(f"{base_file_path.stem}_part_{i + 1}{base_file_path.suffix}")
        split_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_paths.append(split_file_path)

        with open(split_file_path, 'w') as f:
            for url in urls:
                f.write(f"https://tidal.com/browse/track/{url}\n")

        logger.info(f"Saved Tidal URLs to {split_file_path}")

    return file_paths


def download_tracks_from_file(file_path: Path, retry_count: int = 0):
    """
    Download tracks from the specified file using the streamrip tool.

    Args:
        file_path (Path): Path to the file containing Tidal track URLs.
        retry_count (int): Number of retries in case of a failure.

    Raises:
        Exception: If download fails after the maximum number of retries.
    """
    logger.info(f"Starting download from file: {file_path}")

    runner = CliRunner()
    result = runner.invoke(
        rip,
        [
            "--folder", DOWNLOAD_PATH,
            "--no-db",
            "--quality", "3",
            "--verbose",
            "file",
            str(file_path),
        ],
    )

    if "ERROR" in result.output:
        logger.warning("Error(s) occurred during download:")
        logger.warning(result.output)

    if result.exit_code != 0:
        if retry_count < 3:
            return download_tracks_from_file(file_path, retry_count + 1)
        else:
            logger.error("Maximum retries reached. Download failed.")
            raise Exception(f"Download failed for {file_path.name}.")
    else:
        logger.success(f"Download completed successfully for {file_path.name}.")


def process_and_download_tracks_concurrently(tidal_urls: list, workers: int = 1):
    """
    Process and download Tidal tracks concurrently.

    Args:
        tidal_urls (list): List of Tidal track URLs.
        workers (int): Number of concurrent workers to use for downloading.
    """
    file: Path = Path(tempfile.gettempdir()) / f"tidal_urls_{uuid.uuid4()}.txt"
    file.parent.mkdir(parents=True, exist_ok=True)
    with open(file, "w") as f:
        for url in tidal_urls:
            f.write(f"https://tidal.com/browse/track/{url}\n")

    download_tracks_from_file(file)
    file.unlink()

    # file_path = DOWNLOAD_PATH / "tidal_urls.txt"
    # workers = 1  # Set to 1 due to a known issue with multiple workers.

    # split_file_paths = save_tidal_urls_to_file(tidal_urls, file_path, workers)
    # download_tracks_from_file(split_file_paths[0])

    # Concurrent downloading using ProcessPoolExecutor (currently disabled due to issues)
    # with ProcessPoolExecutor(max_workers=workers) as executor:
    #     futures = [executor.submit(download_tracks_from_file, path) for path in split_file_paths]
    #     for future in futures:
    #         try:
    #             future.result()  # Wait for the process to complete and catch any exceptions
    #         except Exception as e:
    #             logger.error(f"Error during download: {e}")
