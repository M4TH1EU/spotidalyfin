# jellyfin_manager.py

import requests
from rich.progress import Progress

from spotidalyfin import cfg
from spotidalyfin.utils.file_utils import resize_image, calculate_checksum, file_to_list, remove_line_from_file, \
    write_line_to_file
from spotidalyfin.utils.formatting import format_string
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

    def request(self, path, method="GET"):
        try:
            url = self.url + "/" + path.lstrip("/")
            if method == "GET":
                return requests.get(url, headers={"X-Emby-Token": self.api_key}).json()
            elif method == "POST":
                return requests.post(url, headers={"X-Emby-Token": self.api_key}).json()
        except requests.exceptions.RequestException as e:
            # TODO: catch exception
            return

    def search(self, query, limit=5, include_item_types="Audio", recursive=True):
        return self.request(
            f"Items?searchTerm={query}&Recursive={recursive}&IncludeItemTypes={include_item_types}&Limit={limit}")

    def search_album(self, album_name, artist_name):
        album_name = format_string(album_name)
        artist_name = format_string(artist_name)

        response = self.search(f"{album_name} {artist_name}", include_item_types="MusicAlbum")
        if response['TotalRecordCount'] > 0:
            for item in response['Items']:
                # TODO: improve search
                if format_string(item['Name']) == album_name and format_string(item['Artists'][0]) == artist_name:
                    return item['Id']

    def search_track_in_album(self, track_name, album_name, artist_name):
        track_name = format_string(track_name)
        album_name = format_string(album_name)
        artist_name = format_string(artist_name)

        album_id = self.search_album(album_name, artist_name)
        if album_id:
            response = self.request(f"Items/{album_id}/Children")
            if response['TotalRecordCount'] > 0:
                for item in response['Items']:
                    # TODO: improve search
                    if item['Type'] == "Audio" and format_string(item['Name']) == track_name:
                        return item['Id']

    def search_track_by_name(self, track_name, artist_name, album_name):
        track_name = format_string(track_name)
        artist_name = format_string(artist_name)
        album_name = format_string(album_name)

        response = self.search(track_name, include_item_types="Audio")
        if response['TotalRecordCount'] > 0:
            for item in response['Items']:
                # TODO: improve search
                if item['Type'] == "Audio" and format_string(item['Name']) == track_name:
                    if format_string(item['Artists'][0]) == artist_name and format_string(item['Album']) == album_name:
                        return item['Id']

    def does_track_exist(self, spotify_track: dict):
        track_name = spotify_track.get('name', '')
        artist_name = spotify_track.get('artists', [{}])[0].get('name', '')
        album_name = spotify_track.get('album', {}).get('name', '')

        find_by_album = self.search_track_in_album(track_name, album_name, artist_name)
        if find_by_album:
            return find_by_album

        find_by_name = self.search_track_by_name(track_name, artist_name, album_name)
        if find_by_name:
            return find_by_name

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
