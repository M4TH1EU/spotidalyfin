import concurrent.futures
import random
import subprocess
import time
from functools import cache
from pathlib import Path

from minim import tidal

from spotidalyfin.utils.logger import log
from ..db.database import Database
from ..utils.comparisons import close, weighted_word_overlap
from ..utils.decorators import rate_limit
from ..utils.formatting import format_artists

QUALITY = {
    "LOW": 1,
    "LOSSLESS": 2,
    "HIRES_LOSSLESS": 3,
    "HI_RES_LOSSLESS": 3,
    "DOLBY_ATMOS": 3,
}


class TidalManager:

    def __init__(self, client_id, client_secret, database: Database = None, country_code=None):
        self.client = tidal.API(
            client_id=client_id,
            client_secret=client_secret
        )

        self.database = database

        if not country_code:
            log.warning("ATTENTION: Country code not set. Defaulting to 'US'.")
            log.warning(
                "THIS MAY CAUSE ISSUES WITH SEARCH RESULTS AND DOWNLOADS. PLEASE SET A COUNTRY CODE IMMEDIATELY!.")
            country_code = 'US'

        self.country_code = country_code

    @rate_limit
    @cache
    def search(self, query, type='TRACKS', limit=5):
        if type == 'ALL':
            return self.client.search(query, limit=limit, country_code=self.country_code)

        res = self.client.search(query, limit=limit, type=type, country_code=self.country_code).get(type.lower(), {})
        return fix_dict(res)

    @rate_limit
    @cache
    def get_track(self, track_id):
        return self.client.get_track(track_id, country_code=self.country_code)

    @rate_limit
    @cache
    def get_album(self, album_id):
        return self.client.get_album(album_id, country_code=self.country_code)

    @rate_limit
    @cache
    def get_album_tracks(self, album_id):
        return fix_dict(self.client.get_album_items(album_id, country_code=self.country_code).get('data', []))

    @rate_limit
    def search_albums(self, album_name: str = None, artist_name: str = None, barcode=None) -> list:
        if barcode:
            res = fix_dict(self.client.get_album_by_barcode_id(barcode, country_code=self.country_code).get('data', []))
            if res:
                return res
        if album_name and artist_name:
            res = self.search(f"{album_name} {artist_name}", type='ALBUMS')
            if res:
                return res

        return []

    @rate_limit
    def search_tracks(self, track_name: str = None, artist_name: str = None, isrc: str = None) -> list:
        if isrc:
            res = fix_dict(self.client.get_tracks_by_isrc(isrc.upper(), country_code=self.country_code).get('data', []))
            if res:
                return res

        if track_name and artist_name:
            res = self.search(f"{track_name} {artist_name}")
            if res:
                return res

        return []

    def search_track_in_album(self, album_id: str, spotify_track: dict) -> dict | None:
        tidal_tracks = self.get_album_tracks(album_id)
        for track in tidal_tracks:
            if get_track_matching_score(track, spotify_track) >= 4:
                return track

        return None

    def search_spotify_track(self, spotify_track: dict, quality=3):
        track_name = spotify_track.get('name', '')
        artist_name = format_artists(spotify_track.get('artists', [{}]), lower=False)[0]
        album_name = spotify_track.get('album', {}).get('name', '')
        album_barcode = spotify_track.get('album', {}).get('external_ids', {}).get('upc', '')
        isrc = spotify_track.get('external_ids', {}).get('isrc', '').upper()

        if track_name and artist_name and album_name:
            matches = []

            # Collect results using concurrent futures to perform async API calls
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                if isrc:
                    futures.append(executor.submit(self.search_tracks, isrc=isrc))
                if album_barcode:
                    futures.append(executor.submit(self.search_albums, barcode=album_barcode))
                futures.append(executor.submit(self.search_tracks, track_name=track_name, artist_name=artist_name))

                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            # Process each result
            for tidal_tracks in results:
                if tidal_tracks and isinstance(tidal_tracks, list):
                    # Track
                    if 'type' not in tidal_tracks[0]:
                        best_track = get_best_match(tidal_tracks, spotify_track)
                        if best_track.get('quality') >= quality and best_track.get('score') >= 3.5:
                            return best_track.get('id')
                        if best_track not in matches:
                            matches.append(best_track)
                    # Album
                    elif 'type' in tidal_tracks[0] and tidal_tracks[0]['type'] == 'album':
                        track = self.search_track_in_album(tidal_tracks[0].get('id', ''), spotify_track)
                        if track:
                            if get_track_quality(track) >= quality:
                                return track.get('id')
                            if track not in matches:
                                matches.append(track)

            if matches:
                return get_best_match(matches, spotify_track).get('id')

            return None


def get_best_match(tidal_tracks: list, spotify_track: dict) -> dict:
    """Get the best match from a list of Tidal tracks based on a Spotify track."""
    matches = []
    best_quality = -1

    for track in tidal_tracks:
        track['score'] = get_track_matching_score(track, spotify_track)
        track['quality'] = get_track_quality(track)

        if track['score'] < 3.5:
            continue

        if track['quality'] > best_quality:
            best_quality = track['quality']
            matches = [track]
        elif track['quality'] == best_quality:
            matches.append(track)

    if matches:
        return max(matches, key=lambda x: x['score'])

    return tidal_tracks[0]


def get_track_matching_score(tidal_track: dict, spotify_track: dict) -> float:
    """Calculate the matching score between a Tidal track and a Spotify track."""
    score = 0  # max : 5

    if close(tidal_track.get('duration', 0), spotify_track.get('duration_ms', 0) / 1000):
        score += 1

    if tidal_track.get('isrc').upper() == spotify_track.get('external_ids', {}).get('isrc', '').upper():
        score += 0.5

    if weighted_word_overlap(tidal_track.get('title', ''), spotify_track.get('name', '')) > 0.7:
        score += 1

    if weighted_word_overlap(tidal_track.get('album', {}).get('title', ''),
                             spotify_track.get('album', {}).get('name', '')) > 0.35:
        score += 1.5

    if all(artist in format_artists(tidal_track.get('artists', [])) for artist in
           format_artists(spotify_track.get('artists', []))):
        score += 1

    return score


def get_track_quality(track: dict, return_as_str: bool = False) -> int | str:
    """Get the quality of a track."""
    qualities = {
        "DOLBY_ATMOS": 0,
        "LOW": 1,
        "LOSSLESS": 2,
        "HIRES_LOSSLESS": 3,
        "HI_RES_LOSSLESS": 3
    }

    if len(track.get('mediaMetadata', {}).get('tags', [])) == 0:
        return "UNKNOWN" if return_as_str else 0

    if return_as_str:
        return track.get('mediaMetadata', {}).get('tags', [])[0]

    return qualities.get(track.get('mediaMetadata', {}).get('tags', [])[0], 0)


def download_tracks(tracks: list[dict], streamrip_path: Path, download_path: Path, quality=3, retry_count=0):
    tmp_file = (download_path / ".tmp-urls")
    tmp_file.parent.mkdir(parents=True, exist_ok=True)

    with open(tmp_file, 'w') as f:
        for track in tracks:
            f.write(f"https://tidal.com/browse/track/{track}\n")

    args = [
        "--folder", str(download_path),
        "--no-db",
        "--quality", str(quality),
        "--verbose",
        "file", str(tmp_file),
    ]

    process = subprocess.Popen(
        [streamrip_path, *args],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    result = process.communicate()

    if process.returncode != 0:
        if retry_count < 3:
            wait = 2 ** retry_count + random.uniform(0.7, 2)
            log.warning(f"An error occurred during download. Retrying in {wait} sec...")
            time.sleep(wait)
            return download_tracks(tracks=tracks, streamrip_path=streamrip_path, download_path=download_path,
                                   quality=quality, retry_count=retry_count + 1)
        else:
            log.error("Maximum retries reached. Download failed.")
            log.debug("Streamrip log begins below:")
            log.debug(result[0].decode())
            log.debug(result[1].decode())
            log.debug("Streamrip log ends above.")
            raise Exception(f"Download failed.")
    else:
        log.info("Download completed successfully")
        tmp_file.unlink()


def fix_dict(res: dict | list) -> list:
    return [item['resource'] for item in res]
