# cli.py
import argparse

from constants import DOWNLOAD_PATH, TIDAL_CLIENT_ID, TIDAL_CLIENT_SECRET, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from spotify_manager import get_spotify_client, get_playlist_tracks, get_liked_songs
from tidal_manager import get_tidal_client, search_tidal_track, save_tidal_urls_to_file, download_tracks_from_file


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

        print(f"Processing: {track_name} - {artist_name} ({album_name})")

        tidal_track_id = search_tidal_track(client_tidal, track_name, artist_name, album_name, duration)
        if tidal_track_id:
            tidal_urls.append(tidal_track_id)
        else:
            print("  Track not found.")

    if tidal_urls:
        file_path = DOWNLOAD_PATH / "tidal_urls.txt"
        save_tidal_urls_to_file(tidal_urls, file_path)
        download_tracks_from_file(file_path)


def download_playlists_from_file(file_path):
    with open(file_path, 'r') as f:
        playlist_ids = f.read().splitlines()

    for playlist_id in playlist_ids:
        download_playlist(playlist_id)


if __name__ == '__main__':
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
