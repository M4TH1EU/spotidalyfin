# tidal_manager.py
import random
import sys
import time

from minim import tidal
from tidal_dl_ng import cli as tidal_dl_ng

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
            print(f"Rate limit hit, retrying in {backoff_time:.2f} seconds...")
            time.sleep(backoff_time)
            return search_tidal_track(client, track_name, artist_name, album_name, duration, retry_count + 1)
        else:
            print(f"Failed to search track: {e}")
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


def save_tidal_urls_to_file(tidal_urls, file_path):
    with open(file_path, 'w') as f:
        for url in tidal_urls:
            f.write(f"https://tidal.com/browse/track/{url}\n")


def download_tracks_from_file(file_path):
    sys.argv = ["tidal-dl-ng", "dl", file_path]
    try:
        tidal_dl_ng.app()
    except SystemExit as e:
        if e.code != 0:
            print(f"Download failed with error code: {e.code}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def download_track_from_tidal(track_id: str):
    sys.argv = ["tidal-dl-ng", "dl", f"https://tidal.com/browse/track/{track_id}"]
    try:
        tidal_dl_ng.app()
    except SystemExit as e:
        if e.code != 0:
            print(f"Download failed with error code: {e.code}")
    except Exception as e:
        print(f"Unexpected error: {e}")
