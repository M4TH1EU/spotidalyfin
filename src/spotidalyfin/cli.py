# cli.py
import argparse

from loguru import logger

from constants import DOWNLOAD_PATH, TIDAL_CLIENT_ID, TIDAL_CLIENT_SECRET, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from spotify_manager import get_spotify_client, get_playlist_tracks, get_liked_songs
from src.spotidalyfin.file_manager import organize_track
from src.spotidalyfin.jellyfin_manager import search_jellyfin
from src.spotidalyfin.utils import setup_logger
from tidal_manager import get_tidal_client, search_tidal_track, process_and_download_tracks_concurrently


def download_liked_songs():
    client_spotify = get_spotify_client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    liked_tracks = get_liked_songs(client_spotify)
    process_tracks(liked_tracks)


def download_playlist(playlist_id):
    client_spotify = get_spotify_client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    playlist_tracks = get_playlist_tracks(client_spotify, playlist_id)
    process_tracks(playlist_tracks)


def process_tracks(tracks):
    client_tidal = get_tidal_client(TIDAL_CLIENT_ID, TIDAL_CLIENT_SECRET)
    tidal_urls = []

    for track in tracks:
        track_info = track['track']
        track_name = track_info['name']
        artist_name = track_info['artists'][0]['name']
        album_name = track_info['album']['name']
        duration = int(track_info['duration_ms']) / 1000

        print()
        logger.info(f"Processing: {track_name} - {artist_name} ({album_name})")

        jellyfin_id = search_jellyfin(track_name, artist_name, album_name)
        if not jellyfin_id:
            logger.info(f"Track not found (Jellyfin)")
            tidal_track_id = search_tidal_track(client_tidal, track_name, artist_name, album_name, duration)
            if tidal_track_id:
                tidal_urls.append(tidal_track_id)
                logger.success("Track found on Tidal")
            else:
                logger.warning("Track not found on Tidal")
        else:
            logger.success(f"Track already exists (Jellyfin)")

    if tidal_urls:
        process_and_download_tracks_concurrently(tidal_urls)
        organize_downloaded_tracks()


def organize_downloaded_tracks():
    logger.info(f"Organizing tracks in {DOWNLOAD_PATH}")
    for track_path in DOWNLOAD_PATH.glob("*"):
        if track_path.is_file() and "m4a" in track_path.suffix:
            organize_track(track_path)
            logger.info(f"Organized: {track_path.name}")


def download_playlists_from_file(file_path):
    logger.info(f"Reading playlist IDs from file: {file_path}")
    with open(file_path, 'r') as f:
        playlist_ids = f.read().splitlines()

    for playlist_id in playlist_ids:
        logger.info(f"Processing playlist: {playlist_id}")
        download_playlist(playlist_id)


if __name__ == '__main__':
    setup_logger()

    parser = argparse.ArgumentParser(description="Download music from Spotify and Tidal.")
    parser.add_argument("--liked", action="store_true", help="Download liked songs from Spotify")
    parser.add_argument("--playlist", type=str, help="Download a single playlist by Spotify ID or URL")
    parser.add_argument("--file", type=str, help="Download playlists listed in a text file")

    args = parser.parse_args()

    if args.liked:
        download_liked_songs()
    elif args.playlist:
        download_playlist(args.playlist)
    elif args.file:
        download_playlists_from_file(args.file)
    else:
        parser.print_help()
