# cli.py
import argparse

from loguru import logger

from spotidalyfin import database
from spotidalyfin.constants import TIDAL_CLIENT_ID, TIDAL_CLIENT_SECRET, SPOTIFY_CLIENT_ID, \
    SPOTIFY_CLIENT_SECRET
from spotidalyfin.file_manager import check_downloaded_tracks, organize_downloaded_tracks
from spotidalyfin.jellyfin_manager import search_jellyfin
from spotidalyfin.spotify_manager import get_spotify_client, get_playlist_tracks, get_liked_songs
from spotidalyfin.tidal_manager import get_tidal_client, process_and_download_tracks_concurrently, \
    get_tidal_url_from_cache_or_search
from spotidalyfin.utils import setup_logger, log_not_found_tracks


def download_liked_songs():
    client_spotify = get_spotify_client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    liked_tracks = get_liked_songs(client_spotify)
    process_tracks(liked_tracks)


def download_playlist(playlist_id):
    client_spotify = get_spotify_client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    playlist_tracks = get_playlist_tracks(client_spotify, playlist_id)
    process_tracks(playlist_tracks)


def download_playlists_from_file(file_path):
    logger.debug(f"Reading playlist IDs from file: {file_path}")
    with open(file_path, 'r') as f:
        playlist_ids = f.read().splitlines()

    for playlist_id in playlist_ids:
        logger.info(f"Processing playlist: {playlist_id}")
        download_playlist(playlist_id)


def download_track(track_id):
    client_spotify = get_spotify_client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    track = client_spotify.get_track(track_id)
    process_tracks([track])


def process_tracks(spotify_tracks):
    client_tidal = get_tidal_client(TIDAL_CLIENT_ID, TIDAL_CLIENT_SECRET)
    tidal_urls = []
    not_found = []

    for spotify_track in spotify_tracks:
        if len(spotify_tracks) > 1:
            spotify_track = spotify_track.get('track', {})

        track_name = spotify_track.get('name', '')
        artist_name = spotify_track.get('artists', [{}])[0].get('name', '')
        album_name = spotify_track.get('album', {}).get('name', '')
        track_id = spotify_track.get('id', '')

        jellyfin_id = search_jellyfin(track_name, artist_name, album_name)

        if jellyfin_id:
            logger.debug(f"Track already exists (Jellyfin): {track_name} - {artist_name} ({album_name})")
            continue

        logger.info(f"Searching for : {track_name} - {artist_name} ({album_name})")

        tidal_url = get_tidal_url_from_cache_or_search(track_id, spotify_track, client_tidal)

        if tidal_url:
            tidal_urls.append(tidal_url)
        else:
            not_found.append(spotify_track)

    log_not_found_tracks(not_found)

    if tidal_urls:
        process_and_download_tracks_concurrently(tidal_urls)
        check_downloaded_tracks(tidal_urls)
        organize_downloaded_tracks()

    logger.success("Finished.")


if __name__ == '__main__':
    setup_logger()
    database.initialize_database()

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
