import concurrent
from functools import cache
from pathlib import Path
from typing import Optional, List, Any

import requests
import tidalapi
from tidalapi import Quality, media, album, Track, Album
from tidalapi.session import SearchResults

from spotidalyfin.utils.comparisons import close, weighted_word_overlap
from spotidalyfin.utils.decorators import rate_limit
from spotidalyfin.utils.decryption import decrypt_security_token, decrypt_file
from spotidalyfin.utils.file_utils import extract_flac_from_mp4
from spotidalyfin.utils.formatting import format_artists
from spotidalyfin.utils.logger import log
from spotidalyfin.utils.metadata import set_audio_tags, organize_audio_file

QUALITIES = {
    "DOLBY_ATMOS": 0,
    "LOW": 1,
    "LOSSLESS": 2,
    "HIRES_LOSSLESS": 3,
    "HI_RES_LOSSLESS": 3
}


class TidalManager:

    def __init__(self, session_file: Path):
        self.client = tidalapi.Session()
        self.client.login_session_file(session_file, do_pkce=True)
        self.client.audio_quality = Quality.hi_res_lossless

    @rate_limit
    @cache
    def get_track(self, track_id) -> Track:
        return self.client.track(track_id)

    @rate_limit
    @cache
    def get_album(self, album_id) -> Album:
        return self.client.album(album_id)

    @rate_limit
    @cache
    def search(self, query, models: Optional[List[Optional[Any]]] = None, limit=15) -> SearchResults:
        if len(query) > 99:
            query = query[:99]

        if not models:
            models = [media.Track]

        return self.client.search(query, limit=limit, models=models)

    @rate_limit
    @cache
    def get_album_tracks(self, album_id) -> list[Track]:
        return self.client.album(album_id).tracks()

    @rate_limit
    def search_albums(self, album_name: str = None, artist_name: str = None, barcode=None) -> list[Album]:
        if barcode:
            res = self.client.get_albums_by_barcode(barcode)
            if res:
                return res
        if album_name and artist_name:
            res = self.search(f"{album_name} {artist_name}", models=[album.Album]).get('albums')
            if res:
                return res
        return []

    @rate_limit
    def search_tracks(self, track_name: str = None, artist_name: str = None, isrc: str = None) -> list[Track]:
        if isrc:
            res = self.client.get_tracks_by_isrc(isrc.upper())
            if res:
                return res

        if track_name and artist_name:
            res = self.search(f"{track_name} {artist_name}").get('tracks')
            if res:
                return res

        return []

    def search_for_track_in_album(self, album: Album, spotify_track: dict) -> Track:
        for track in album.tracks():
            if get_track_matching_score(track, spotify_track) >= 4:
                # Get the real quality of the track
                track.real_quality = track.get_stream().audio_quality
                track.real_quality_score = QUALITIES.get(track.real_quality)
                return track

    def search_spotify_track(self, spotify_track: dict, quality=3) -> Track:
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
            for result in results:
                if result and isinstance(result, list):
                    # Track
                    if isinstance(result[0], Track):
                        best_track = get_best_match(result, spotify_track)
                        if best_track.real_quality_score >= quality and best_track.score >= 3.5:
                            return best_track
                        if best_track not in matches:
                            matches.append(best_track)
                    # Album
                    elif isinstance(result[0], Album):
                        for album in result:
                            track = self.search_for_track_in_album(album, spotify_track)
                            if track:
                                if track.real_quality_score >= quality:
                                    return track
                                if track not in matches:
                                    matches.append(track)

            if matches:
                return get_best_match(matches, spotify_track)

            return None

    def download_track(self, track: Track, download_path: Path = None, output_dir: Path = None):
        stream_manifest = track.get_stream().get_stream_manifest()
        download_urls = stream_manifest.get_urls()
        suffix = "m4a" if stream_manifest.mime_type.split("/")[
                              -1] == "mp4" else "unknown"  # TODO: get more knowledge about this
        path_file = download_path / f"{track.id}.{suffix}"

        # TODO: check why ??
        # if len(download_urls) == 1:
        #     r = requests.get(download_urls[0], stream=True, timeout=10)
        #     r.raise_for_status()

        if not path_file.exists():
            # TODO: progress bar
            with open(path_file, "wb") as f:
                for url in download_urls:
                    r = requests.get(url, stream=True, timeout=10)
                    r.raise_for_status()
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            log.debug("Downloaded track.")

            if stream_manifest.is_encrypted:
                # TODO: convert Pathlib
                key, nonce = decrypt_security_token(stream_manifest.encryption_key)
                tmp_path_file_decrypted = str(path_file) + "_decrypted"
                decrypt_file(str(path_file), tmp_path_file_decrypted, key, nonce)

        # TODO: extract flac from mp4 option ?
        if suffix == "m4a":
            log.debug("Extracting flac from m4a...")
            path_file = extract_flac_from_mp4(path_file)
            if path_file.exists():
                log.debug("Setting audio tags...")
                tags = set_audio_tags(path_file, track)
                organize_audio_file(file_path=path_file, output_dir=output_dir, metadata=tags)


def get_best_match(tidal_tracks: list[Track], spotify_track: dict) -> Track:
    """Get the best match from a list of Tidal tracks based on a Spotify track."""

    matches = []
    best_quality = -1

    for track in tidal_tracks:
        track.score = get_track_matching_score(track, spotify_track)
        track.real_quality = track.get_stream().audio_quality
        track.real_quality_score = QUALITIES.get(track.real_quality)

        if track.score < 3.5:
            continue

        if track.real_quality_score >= best_quality:
            best_quality = QUALITIES.get(track.real_quality)
            matches = track
        elif track.real_quality_score == best_quality:
            matches.append(track)

    if matches and isinstance(matches, list):
        return max(matches, key=lambda x: x.score)
    elif matches and isinstance(matches, Track):
        return matches
    else:
        return tidal_tracks[0]


def get_track_matching_score(track: Track, spotify_track: dict) -> float:
    """Calculate the matching score between a Tidal track and a Spotify track."""
    score = 0  # max : 5

    if close(track.duration, spotify_track.get('duration_ms', 0) / 1000):
        score += 1

    if track.isrc.upper() == spotify_track.get('external_ids', {}).get('isrc', '').upper():
        score += 0.5

    if weighted_word_overlap(track.full_name, spotify_track.get('name', '')) > 0.7:
        score += 1

    if weighted_word_overlap(track.album.name, spotify_track.get('album', {}).get('name', '')) > 0.35:
        score += 1.5

    if all(artist in format_artists(track.artists) for artist in
           format_artists(spotify_track.get('artists', []))):
        score += 1

    return score
