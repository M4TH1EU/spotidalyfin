import concurrent
from pathlib import Path
from typing import Optional, List, Any

import cachebox
import requests
import tidalapi
from tidalapi import Quality, media, album, Track, Album
from tidalapi.session import SearchResults

from spotidalyfin.cfg import QUALITIES
from spotidalyfin.utils.decorators import rate_limit
from spotidalyfin.utils.decryption import decrypt_security_token, decrypt_file
from spotidalyfin.utils.file_utils import extract_flac_from_mp4
from spotidalyfin.utils.formatting import format_artists
from spotidalyfin.utils.logger import log
from spotidalyfin.utils.metadata import set_audio_tags, organize_audio_file
from spotidalyfin.utils.tidal_track_utils import get_best_match, get_real_audio_quality, get_track_matching_score, \
    get_stream


class TidalManager:

    def __init__(self, session_file: Path):
        self.client = tidalapi.Session()
        self.client.login_session_file(session_file, do_pkce=True)
        self.client.audio_quality = Quality.hi_res_lossless

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_track(self, track_id) -> Track:
        return self.client.track(track_id)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_album(self, album_id) -> Album:
        return self.client.album(album_id)

    @cachebox.cached(cachebox.LRUCache(maxsize=128))
    @rate_limit
    def search(self, query, models: Optional[List[Optional[Any]]] = None, limit=7) -> SearchResults:
        if len(query) > 99:
            query = query[:99]

        if not models:
            models = [media.Track]

        return self.client.search(query, limit=limit, models=models)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_album_tracks(self, album: Album) -> list[Track]:
        return album.tracks()

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
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

    @cachebox.cached(cachebox.LRUCache(maxsize=128))
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
        for track in self.get_album_tracks(album):
            if get_track_matching_score(track, spotify_track) >= 4:
                return track

    def search_spotify_track(self, spotify_track: dict, quality=3) -> Track:
        """
        Search for a Spotify track on Tidal and return the best match using various search methods.

        :param spotify_track: Spotify track to search for
        :param quality: Minimum quality score to consider a match

        :return: Best match found on Tidal :class:`Track`
        """
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
                                if QUALITIES.get(get_real_audio_quality(track)) >= quality:
                                    return track
                                if track not in matches:
                                    matches.append(track)

            if matches:
                return get_best_match(matches, spotify_track)

            return None

    def download_track(self, track: Track, download_path: Path = None, output_dir: Path = None):
        stream_manifest = get_stream(track).get_stream_manifest()
        download_urls = stream_manifest.get_urls()
        tmp_file = download_path / f"{track.id}.tmp"
        tmp_file.parent.mkdir(parents=True, exist_ok=True)

        # TODO: check why ??
        # if len(download_urls) == 1:
        #     r = requests.get(download_urls[0], stream=True, timeout=10)
        #     r.raise_for_status()

        if not tmp_file.exists():
            # TODO: progress bar
            with open(tmp_file, "wb") as f:
                for url in download_urls:
                    r = requests.get(url, stream=True, timeout=10)
                    r.raise_for_status()
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            log.debug("Downloaded track.")

            if stream_manifest.is_encrypted:
                log.debug("Decrypting track...")
                # TODO: convert Pathlib / make it work
                key, nonce = decrypt_security_token(stream_manifest.encryption_key)
                tmp_path_file_decrypted = str(tmp_file) + "_decrypted"
                decrypt_file(str(tmp_file), tmp_path_file_decrypted, key, nonce)

        mime_type = stream_manifest.mime_type.split("/")[-1]
        # TODO: extract flac from mp4 option ?
        # Extract flac from mp4 container
        if mime_type == "mp4":
            log.debug("Extracting flac from m4a...")
            tmp_file = extract_flac_from_mp4(tmp_file)

        # Metadata and move file to output directory
        if tmp_file.exists():
            log.debug("Setting audio tags...")
            tags = set_audio_tags(tmp_file, track)
            organize_audio_file(file_path=tmp_file, output_dir=output_dir, metadata=tags)
