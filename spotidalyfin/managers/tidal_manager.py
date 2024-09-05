import concurrent
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, List, Any

import cachebox
import requests
import tidalapi
from rich.progress import Progress
from tidalapi import Quality, album, Album
from tidalapi import Track, media
from tidalapi.exceptions import MetadataNotAvailable
from tidalapi.session import SearchResults

from spotidalyfin import cfg
from spotidalyfin.cfg import QUALITIES
from spotidalyfin.utils.comparisons import weighted_word_overlap, close
from spotidalyfin.utils.decorators import rate_limit
from spotidalyfin.utils.decryption import decrypt_security_token, decrypt_file
from spotidalyfin.utils.file_utils import extract_flac_from_mp4
from spotidalyfin.utils.formatting import format_artists
from spotidalyfin.utils.logger import log
from spotidalyfin.utils.metadata import set_audio_tags, organize_audio_file


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
            if self.get_track_matching_score(track, spotify_track) >= 4:
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
            with ThreadPoolExecutor(max_workers=3) as executor:
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
                        best_track = self.get_best_match(result, spotify_track)
                        if best_track.real_quality_score >= quality and best_track.score >= 3.5:
                            return best_track
                        if best_track not in matches:
                            matches.append(best_track)
                    # Album
                    elif isinstance(result[0], Album):
                        for album in result:
                            track = self.search_for_track_in_album(album, spotify_track)
                            if track:
                                if QUALITIES.get(self.get_real_audio_quality(track)) >= quality:
                                    return track
                                if track not in matches:
                                    matches.append(track)

            if matches:
                return self.get_best_match(matches, spotify_track)

            return None

    def get_real_audio_quality(self, track: Track) -> str:
        """Get the real audio quality of a track."""
        if track.is_DolbyAtmos:
            return "DOLBY_ATMOS"
        elif track.is_Mqa:
            return "MQA"
        elif track.is_HiRes:
            return "HI_RES_LOSSLESS"
        else:
            return track.audio_quality

    @cachebox.cached(cachebox.LRUCache(maxsize=64))
    @rate_limit
    def get_stream(self, track: Track) -> media.Stream:
        """Get the stream of a track (uses caching)."""
        return track.get_stream()

    @cachebox.cached(cachebox.LRUCache(maxsize=32))
    def get_lyrics(self, track: Track) -> str:
        """Get the lyrics of a track (uses caching)."""
        try:
            lyrics = track.lyrics()
            return lyrics.subtitles or lyrics.text
        except MetadataNotAvailable:
            return ""

    def get_best_match(self, tidal_tracks: list[Track], spotify_track: dict) -> Track:
        """
        Get the best match from a list of Tidal tracks based on a Spotify track.

        Uses a scoring system and the real audio quality of the tracks to determine the best match.

        Minimum score to consider a match : 3.5
        Highest quality will be prioritized from score >= 3.5
        If multiple tracks have the same quality, the one with the highest score will be returned.

        :param tidal_tracks: List of Tidal tracks to compare :class:`list[Track]`
        :param spotify_track: Spotify track to compare :class:`dict`

        :return: Best match found on Tidal :class:`Track`
        """

        matches = []
        best_quality = -1

        for track in tidal_tracks:
            track.score = self.get_track_matching_score(track, spotify_track)
            track.real_quality = self.get_real_audio_quality(track)
            track.real_quality_score = QUALITIES.get(track.real_quality)
            track.spotify_id = spotify_track.get('id', '')

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

    def get_track_matching_score(self, track: Track, spotify_track: dict) -> float:
        """
        Calculate the matching score between a Tidal track and a Spotify track.

        The score is calculated based on the following criteria:
        - Duration (1 point)
        - ISRC (0.5 point)
        - Title (1 point)
        - Album name (1.5 point)
        - Artists (1 point)

        Minimum score to consider a match : 3.5
        Maximum score : 5

        :param track: Tidal track to compare :class:`Track`
        :param spotify_track: Spotify track to compare :class:`dict`

        """
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

    def download_track(self, track: Track, progress: Progress = None):
        stream_manifest = self.get_stream(track).get_stream_manifest()
        download_urls = stream_manifest.get_urls()
        tmp_file = cfg.get("dl-dir") / f"{track.id}.tmp"
        tmp_file.parent.mkdir(parents=True, exist_ok=True)

        if progress:
            task = progress.add_task(f"Downloading {track.full_name} - {track.artist.name}...",
                                     total=len(download_urls))

        # TODO: check why ??
        # if len(download_urls) == 1:
        #     r = requests.get(download_urls[0], stream=True, timeout=10)
        #     r.raise_for_status()

        with open(tmp_file, "wb") as f:
            for url in download_urls:
                if progress:
                    progress.update(task, advance=1)

                r = requests.get(url, stream=True, timeout=10)
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            log.debug(f"Downloaded track : {track.id}")

        if stream_manifest.is_encrypted:
            log.debug(f"Decrypting track {track.full_name} - {track.artist.name}")
            # TODO: convert Pathlib / make it work
            key, nonce = decrypt_security_token(stream_manifest.encryption_key)
            tmp_path_file_decrypted = str(tmp_file) + "_decrypted"
            decrypt_file(str(tmp_file), tmp_path_file_decrypted, key, nonce)

        mime_type = stream_manifest.mime_type.split("/")[-1]
        # TODO: extract flac from mp4 option ?
        # Extract flac from mp4 container
        if mime_type == "mp4":
            if progress:
                progress.update(task, description="Extracting flac from m4a...")
            log.debug(f"Extracting flac from m4a : {track.id}")
            tmp_file = extract_flac_from_mp4(tmp_file)

        # Metadata and move file to output directory
        if tmp_file.exists():
            if progress:
                progress.update(task, description="Setting audio tags...")
            log.debug(f"Setting audio tags : {track.id}")
            track.lyrics = self.get_lyrics(track)
            tags = set_audio_tags(tmp_file, track)
            organize_audio_file(file_path=tmp_file, output_dir=cfg.get('out-dir'), metadata=tags)

        if progress:
            progress.update(0, advance=1)
            progress.remove_task(task)
