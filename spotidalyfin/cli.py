import argparse
import threading
import time
from queue import Queue

import _queue
from loguru import logger

from spotidalyfin.constants import DOWNLOAD_PATH, TIDAL_CLIENT_ID, TIDAL_CLIENT_SECRET, SPOTIFY_CLIENT_ID, \
    SPOTIFY_CLIENT_SECRET, TIDAL_DL_NG_CONFIG, TIDAL_DL_NG_PATH
from spotidalyfin.file_manager import organize_track, check_downloaded_tracks, apply_json_config
from spotidalyfin.jellyfin_manager import search_jellyfin
from spotidalyfin.spotify_manager import get_spotify_client, get_playlist_tracks, get_liked_songs
from spotidalyfin.tidal_manager import get_tidal_client, search_tidal_track, process_and_download_tracks_concurrently
from spotidalyfin.utils import setup_logger

# Global queue to store track URLs and a lock to ensure only one download at a time
track_queue = Queue()
download_lock = threading.Lock()


def worker():
    """Thread worker function to process tracks in the queue."""
    while True:
        tidal_urls = []

        # Collect up to X tracks from the queue in a maximum of Y seconds
        for _ in range(8):
            try:
                tidal_track_id = track_queue.get(timeout=16)
                tidal_urls.append(tidal_track_id)
                track_queue.task_done()
            except _queue.Empty:
                break

        if tidal_urls:
            with download_lock:  # Ensure only one download at a time
                process_and_download_tracks_concurrently(tidal_urls)
                check_downloaded_tracks(tidal_urls)
                organize_downloaded_tracks()

        # If there are no more items in the queue, take a break
        if track_queue.empty():
            time.sleep(1)


def download_liked_songs():
    client_spotify = get_spotify_client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    liked_tracks = get_liked_songs(client_spotify)
    process_tracks(liked_tracks)


def download_playlist(playlist_id):
    client_spotify = get_spotify_client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    playlist_tracks = get_playlist_tracks(client_spotify, playlist_id)
    process_tracks(playlist_tracks)


def download_track(track_id):
    client_spotify = get_spotify_client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    track = client_spotify.get_track(track_id)
    process_tracks([track])


def process_tracks(spotify_tracks):
    client_tidal = get_tidal_client(TIDAL_CLIENT_ID, TIDAL_CLIENT_SECRET)

    for spotify_track in spotify_tracks:
        if len(spotify_tracks) > 1:
            spotify_track = spotify_track['track']

        track_name = spotify_track.get('name')
        artist_name = spotify_track.get('artists')[0].get('name')
        album_name = spotify_track.get('album').get('name')

        logger.info(f"Processing: {track_name} - {artist_name} ({album_name})")

        jellyfin_id = search_jellyfin(track_name, artist_name, album_name)
        if not jellyfin_id:
            logger.info(f"Track not found (Jellyfin)")
            tidal_track_id = search_tidal_track(client_tidal, spotify_track)
            if tidal_track_id:
                track_queue.put(tidal_track_id)  # Add track to the queue
                logger.success("Track found on Tidal")
            else:
                logger.warning("Track not found on Tidal")
        else:
            logger.success(f"Track already exists (Jellyfin)")

        print()


def organize_downloaded_tracks():
    logger.info(f"Organizing tracks in {DOWNLOAD_PATH}")
    for track_path in DOWNLOAD_PATH.glob("*.flac"):
        if track_path.is_file():
            organize_track(track_path)
            logger.info(f"Organized: {track_path.name}")

    for track_path in DOWNLOAD_PATH.glob("*.txt"):
        if track_path.is_file():
            track_path.unlink()


def download_playlists_from_file(file_path):
    logger.info(f"Reading playlist IDs from file: {file_path}")
    with open(file_path, 'r') as f:
        playlist_ids = f.read().splitlines()

    for playlist_id in playlist_ids:
        logger.info(f"Processing playlist: {playlist_id}")
        download_playlist(playlist_id)


if __name__ == '__main__':
    setup_logger()
    apply_json_config(TIDAL_DL_NG_CONFIG, TIDAL_DL_NG_PATH)

    # Start worker thread
    threading.Thread(target=worker, daemon=True).start()

    parser = argparse.ArgumentParser(description="Download music from Spotify and Tidal.")
    parser.add_argument("--liked", action="store_true", help="Download liked songs from Spotify")
    parser.add_argument("--playlist", type=str, help="Download a single playlist by Spotify ID or URL")
    parser.add_argument("--file", type=str, help="Download playlists listed in a text file")
    parser.add_argument("--track", type=str, help="Download a single track by Spotify ID or URL")

    args = parser.parse_args()

    if args.liked:
        download_liked_songs()
    elif args.playlist:
        download_playlist(args.playlist)
    elif args.file:
        download_playlists_from_file(args.file)
    elif args.track:
        download_track(args.track)
    else:
        parser.print_help()

    # Wait until all tasks in the queue have been processed
    track_queue.join()
