# tidal_manager.py
import random
import subprocess
import time
from pathlib import Path

from minim import tidal

from spotidalyfin.utils.logger import log
from ..db.database import Database
from ..utils.comparisons import similar, close
from ..utils.decorators import rate_limit
from ..utils.formatting import format_artists

QUALITY = {
    "DOLBY_ATMOS": 0,
    "LOW": 1,
    "LOSSLESS": 2,
    "HIRES_LOSSLESS": 3,
    "HI_RES_LOSSLESS": 3
}


class TidalManager:

    def __init__(self, client_id, client_secret, database: Database = None, country_code=None):
        self.client = tidal.API(
            client_id=client_id,
            client_secret=client_secret
        )

        if database:
            self.database = database

        if not country_code:
            log.warning("ATTENTION: Country code not set. Defaulting to 'US'.")
            log.warning(
                "THIS MAY CAUSE ISSUES WITH SEARCH RESULTS AND DOWNLOADS. PLEASE SET A COUNTRY CODE IMMEDIATELY!.")
            country_code = 'US'

        self.country_code = country_code

    @rate_limit
    def search(self, query, type='TRACKS', limit=5):
        if type == 'ALL':
            return self.client.search(query, limit=limit, country_code=self.country_code)

        res = self.client.search(query, limit=limit, type=type, country_code=self.country_code).get(type.lower(), {})
        return fix_dict(res)

    @rate_limit
    def get_track(self, track_id):
        return self.client.get_track(track_id, country_code=self.country_code)

    @rate_limit
    def get_album(self, album_id):
        return self.client.get_album(album_id, country_code=self.country_code)

    @rate_limit
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
            res = self.search(f"{track_name} {artist_name}", limit=1)
            if res:
                return res

        return []

    def search_spotify_track(self, spotify_track: dict, quality=3):
        track_name = spotify_track.get('name', '')
        artist_name = format_artists(spotify_track.get('artists', [{}]), lower=False)[0]
        album_name = spotify_track.get('album', {}).get('name', '')
        album_barcode = spotify_track.get('album', {}).get('external_ids', {}).get('upc', '')
        isrc = spotify_track.get('external_ids', {}).get('isrc', '').upper()

        if track_name and artist_name and album_name:
            matches = list()

            if isrc:
                tidal_tracks = self.search_tracks(isrc=isrc)
                if tidal_tracks:
                    best_track = get_best_quality_track(tidal_tracks, track_name, artist_name, album_name)
                    if get_track_quality(best_track) >= quality:
                        return best_track.get('id')
                    else:
                        if best_track not in matches:
                            matches.append(best_track)

            if album_barcode:
                tidal_albums = self.search_albums(barcode=album_barcode)
                if tidal_albums:
                    tidal_tracks = self.get_album_tracks(tidal_albums[0].get('id', ''))
                    for track in tidal_tracks:
                        if does_tidal_track_match_spotify_track(track, spotify_track):
                            if get_track_quality(track) >= quality:
                                return track.get('id')
                            else:
                                if track not in matches:
                                    matches.append(track)

            tidal_tracks = self.search_tracks(track_name=track_name, artist_name=artist_name)
            for track in tidal_tracks:
                if does_tidal_track_match_spotify_track(track, spotify_track):
                    if get_track_quality(track) >= quality:
                        return track.get('id')
                    else:
                        if track not in matches:
                            matches.append(track)

            if matches:
                return get_best_quality_track(matches, track_name, artist_name, album_name).get('id')

            return None


def does_tidal_track_match_spotify_track(tidal_track: dict, spotify_track: dict) -> bool:
    """
    Match a Tidal track against a Spotify track based on various criteria.

    Args:
        tidal_track (dict): Tidal track information.
        spotify_track (dict): Spotify track information.

    Returns:
        bool: True if the tracks match based on criteria, False otherwise.
    """
    s = {
        'artists': format_artists(spotify_track.get('artists', [])),
        'album_name': spotify_track.get('album', {}).get('name', '').lower(),
        'track_name': spotify_track.get('name', '').lower(),
        'duration': int(spotify_track.get('duration_ms', 0) / 1000),
        'isrc': spotify_track.get('external_ids', {}).get('isrc')
    }
    t = {
        'artists': format_artists(tidal_track.get('artists', [])),
        'album_name': tidal_track.get('album', {}).get('title', '').lower(),
        'track_name': tidal_track.get('title', '').lower(),
        'duration': tidal_track.get('duration', 0),
        'isrc': tidal_track.get('isrc')
    }

    criteria = 0
    criteria += all(artist in t['artists'] for artist in s['artists'])
    criteria += similar(s['album_name'], t['album_name'])
    criteria += similar(s['track_name'], t['track_name'])
    criteria += close(s['duration'], t['duration'])
    criteria += (s['isrc'] == t['isrc'])

    return criteria >= 4


def get_best_quality_track(tracks: list, track_name: str = None, artist_name: str = None,
                           album_name: str = None) -> dict:
    """Get the best quality track from a list of tracks with similarity consideration for ties."""

    def compute_similarity(track_data: dict) -> float:
        """Calculate similarity score based on track name, artist, and album."""
        return (
                similar(track_name, track_data.get('title', '')) +
                similar(artist_name, format_artists(track_data.get('artists', [""]), lower=False)[0]) +
                similar(album_name, track_data.get('album', {}).get('title', ''))
        )

    best_tracks = []
    best_quality = -1

    for track in tracks:
        quality = get_track_quality(track)

        if quality > best_quality:
            best_quality = quality
            best_tracks = [track]
        elif quality == best_quality:
            best_tracks.append(track)

        if track_name and artist_name and album_name:
            track['similarity'] = compute_similarity(track)

    if best_tracks and track_name and artist_name and album_name:
        return max(best_tracks, key=lambda t: t['similarity'])

    return best_tracks[0] if best_tracks else None


def get_track_quality(track: dict) -> int:
    """Get the quality of a track."""
    qualities = {
        "DOLBY_ATMOS": 0,
        "LOW": 1,
        "LOSSLESS": 2,
        "HIRES_LOSSLESS": 3,
        "HI_RES_LOSSLESS": 3
    }

    return qualities.get(track.get('mediaMetadata', {}).get('tags', [])[0], 0)


def download_tracks(tracks: list[dict], download_path: Path = None, quality=3, retry_count=0):
    tmp_file = (download_path / ".tmp-urls")
    tmp_file.parent.mkdir(parents=True, exist_ok=True)

    with open(tmp_file, 'w') as f:
        for track in tracks:
            f.write(f"https://tidal.com/browse/track/{track}\n")

    # runner = CliRunner()
    # result = runner.invoke(
    #     rip,
    #     [
    #         "--folder", str(download_path),
    #         "--no-db",
    #         "--quality", "3",
    #         # "--verbose",
    #         # "--no-progress"
    #         "file",
    #         str(tmp_file),
    #     ],
    # )

    args = [
        "--folder", str(download_path),
        "--no-db",
        "--quality", "3",
        "--verbose",
        # "--no-progress"
        "file",
        str(tmp_file),
    ]

    process = subprocess.Popen(
        ["/home/mathieu/PycharmProjects/spotify-tidal-jellyfin/bin/streamrip-2.0.5-linux", *args],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    result = process.communicate()

    if process.returncode != 0:
        if retry_count < 3:
            wait = 2 ** retry_count + random.uniform(0.7, 2)
            log.warning(f"An error occurred during download. Retrying in {wait} sec...")
            time.sleep(wait)
            return download_tracks(tracks=tracks, download_path=download_path, quality=quality,
                                   retry_count=retry_count + 1)
        else:
            log.error("Maximum retries reached. Download failed.")
            log.debug("Streamrip log begins below:")
            log.debug(result[0].decode())
            log.debug(result[1].decode())
            log.debug("Streamrip log ends above.")
            raise Exception(f"Download failed.")
    else:
        log.info(f"Download completed successfully")
        tmp_file.unlink()


def fix_dict(res: dict | list) -> list:
    return [item['resource'] for item in res]
