# jellyfin_manager.py
import re
from typing import Optional

import cachebox
import requests
from rich.progress import Progress
from tidalapi import Track

from spotidalyfin import cfg
from spotidalyfin.utils.comparisons import weighted_word_overlap, close
from spotidalyfin.utils.file_utils import resize_image, calculate_checksum, file_to_list, remove_line_from_file, \
    write_line_to_file
from spotidalyfin.utils.formatting import format_artists, normalize_str
from spotidalyfin.utils.logger import log

LIBRARY_MAX_SIZE = (1920, 1080)
PEOPLE_MAX_SIZE = (900, 900)
STUDIO_MAX_SIZE = (1066, 600)


class JellyfinManager:
    def __init__(self, url, api_key):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.metadata_dir = cfg.get("jellyfin-metadata-dir")
        self.checksum_file = self.metadata_dir / ".image_checksums_spotidalyfin_do_not_delete.txt"
        self.checksums = None

    def request(self, path, method="GET", params: dict = {}) -> list:
        url = f"{self.url}/{path.lstrip('/')}"
        headers = {"X-Emby-Token": self.api_key}

        # Fixes an issue with Jellyfin API where searching with apostrophes doesn't work
        if "searchTerm" in params:
            params["searchTerm"] = re.sub(r"['\"’‘”“].*", '', params["searchTerm"])

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, params=params)
            else:
                raise ValueError(f"Invalid method: {method}")

            response.raise_for_status()

            respjson = response.json()
            if respjson.get('TotalRecordCount', 0) >= 1:
                if "Items" in respjson:
                    return respjson["Items"]

            return []
        except requests.exceptions.RequestException:
            return []

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search(self, query=None, limit=5, path="Items", year=None, parent_id=None, include_item_types="Audio",
               recursive=True) -> Optional[list]:
        params = {
            "Recursive": recursive,
            "IncludeItemTypes": include_item_types,
            "Limit": limit
        }
        if query:
            params["searchTerm"] = query
        if year:
            params["years"] = year
        if parent_id:
            params["parentId"] = parent_id

        return self.request(path, params=params)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search_by_parent_id(self, parent_id, limit=5, include_item_types="Audio", recursive=True) -> Optional[list]:
        return self.search(limit=limit, path=f"Items", parent_id=parent_id,
                           include_item_types=include_item_types,
                           recursive=recursive)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search_artist(self, artist_name) -> Optional[dict]:
        response = self.search(query=artist_name, include_item_types="MusicArtist")
        for item in response:
            if weighted_word_overlap(item['Name'], artist_name) > 0.9:
                return item

        return None

    def search_track_for_artist(self, track_name, artist: dict) -> Optional[dict]:
        if artist:
            response = self.search_by_parent_id(artist.get('Id'), include_item_types="Audio")
            for item in response:
                if weighted_word_overlap(item['Name'], track_name) >= 0.66:
                    return item

        return None

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search_album(self, album_name, artist_name=None) -> Optional[dict]:
        response = self.search(query=album_name, include_item_types="MusicAlbum")
        if not response:
            album_name = normalize_str(album_name, remove_in_brackets=False, try_fix_track_name=True)
            response = self.search(query=album_name, include_item_types="MusicAlbum")
            if not response:
                album_name = normalize_str(album_name, remove_in_brackets=True, try_fix_track_name=True)
                response = self.search(query=album_name, include_item_types="MusicAlbum")

        for item in response:
            jellyfin_album_name = item['Name']
            jellyfin_artist_name = format_artists(item['Artists'])[0]

            if weighted_word_overlap(jellyfin_album_name, album_name) >= 0.66:
                if not artist_name or weighted_word_overlap(jellyfin_artist_name, artist_name) >= 0.66:
                    return item

        return None

    def search_track_in_album(self, track_name, album: dict, duration=None):
        response = self.search_by_parent_id(album.get('Id'))
        for item in response:
            jellyfin_track_name = item['Name']
            jellyfin_duration = item.get('RunTimeTicks', 0) / 10000000

            if weighted_word_overlap(jellyfin_track_name, track_name) >= 0.66:
                if not duration or close(jellyfin_duration, duration):
                    return item

        return None

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search_track_by_name(self, track_name, artist_name=None, album_name=None, duration=None,
                             validate_track_name: bool = True) -> Optional[dict]:
        response = self.search(query=track_name, include_item_types="Audio")
        if not response:
            track_name = normalize_str(track_name, remove_in_brackets=False, try_fix_track_name=True)
            response = self.search(query=track_name, include_item_types="Audio")

            if not response:
                track_name = normalize_str(track_name, remove_in_brackets=True, try_fix_track_name=True)
                response = self.search(query=track_name, include_item_types="Audio")

        for item in response:
            jellyfin_track_name = normalize_str(item['Name'], try_fix_track_name=True)
            jellyfin_artist_name = format_artists(item['Artists'])[0]
            jellyfin_album_name = normalize_str(item.get('Album', ''))
            jellyfin_duration = item.get('RunTimeTicks', 0) / 10000000

            if not validate_track_name or weighted_word_overlap(jellyfin_track_name, track_name) >= 0.66:
                if not artist_name or weighted_word_overlap(jellyfin_artist_name, artist_name) >= 0.66:
                    if not album_name or weighted_word_overlap(jellyfin_album_name, album_name) >= 0.66:
                        if not duration or close(jellyfin_duration, duration):
                            return item

        return None

    def does_track_exist(self, track: dict | Track) -> bool:
        if isinstance(track, Track):
            track_name = track.full_name
            artist_name = track.artist.name
            album_name = track.album.name
            duration = track.duration
        else:
            track_name = track.get('name', '')
            artist_name = format_artists(track.get('artists', [{}]), lower=False)[0]
            album_name = track.get('album', {}).get('name', '')
            duration = track.get('duration_ms', 0) / 1000
        # year = spotify_track.get('album', {}).get('release_date', '')[:4]

        # Search for album from artist and then track name in album
        jellyfin_album = self.search_album(album_name, artist_name) or self.search_album(album_name, "")
        if jellyfin_album:
            jellyfin_track = self.search_track_in_album(track_name, jellyfin_album, duration)
            if jellyfin_track:
                return True

        # Search by track name and verify artist name and album name
        jellyfin_track = self.search_track_by_name(track_name, artist_name, album_name, duration)
        if not jellyfin_track:
            # For when the album name might be too different, just search by track name and artist name
            jellyfin_track = self.search_track_by_name(track_name, artist_name, None, duration)
            if not jellyfin_track:
                # Last resort, search by artist name and then track name
                jellyfin_track = self.search_track_by_name(
                    normalize_str(track_name, try_fix_track_name=True, remove_in_brackets=True, stop_at_dash_char=True),
                    artist_name, None)

        if jellyfin_track:
            return True

        return False

    def compress_metadata_images(self, progress: Progress = None):
        library = self.metadata_dir / "library"
        people = self.metadata_dir / "People"
        studio = self.metadata_dir / "Studio"
        artists = self.metadata_dir / "artists"

        self.checksums = file_to_list(self.checksum_file)
        checksums_to_replace = {}

        size_before = sum(file.stat().st_size for file in self.metadata_dir.glob("**/*") if file.is_file())

        for directory in [library, people, studio, artists]:
            if directory == library:
                max_size = LIBRARY_MAX_SIZE
            elif directory == people:
                max_size = PEOPLE_MAX_SIZE
            elif directory == studio:
                max_size = STUDIO_MAX_SIZE
            else:
                max_size = None

            # Get all files in the directory
            glob = list(directory.glob("**/*"))
            glob = [file for file in glob if file.is_file() and file.suffix in [".jpg", ".jpeg", ".png"]]

            # Add progress bar if available
            if progress:
                task = progress.add_task(f"Compressing images in {directory.name}...", total=len(glob))

            for file in glob:

                checksum = calculate_checksum(file)
                if checksum in self.checksums:
                    log.debug(f"Skipping already processed image: {file}")
                    continue

                log.debug(f"Compressing/resizing image: {file}")

                resize_image(file, max_size, quality=45)
                new_checksum = calculate_checksum(file)

                checksums_to_replace[checksum] = new_checksum

                if progress:
                    progress.advance(task, advance=1)

        # Replace old checksums (uncompressed) with new checksums for compressed images
        for checksum, new_checksum in checksums_to_replace.items():
            remove_line_from_file(self.checksum_file, checksum)
            write_line_to_file(self.checksum_file, new_checksum)

        size_after = sum(file.stat().st_size for file in self.metadata_dir.glob("**/*") if file.is_file())

        if size_after < size_before:
            log.info(f"[bold green]Compressed metadata images. Size before: {size_before / 1024 / 1024:.2f} MB, "
                     f"size after: {size_after / 1024 / 1024:.2f} MB", extra={"markup": True})
