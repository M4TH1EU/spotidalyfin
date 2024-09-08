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
    write_line_to_file, get_as_base64
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

    def request(self, path, method="GET", params: dict = {}, image_data: bytes = None) -> list:
        url = f"{self.url}/{path.lstrip('/')}"
        headers = {"X-Emby-Token": self.api_key}

        if image_data:
            headers["Content-Type"] = "image/jpeg"

        # Fixes an issue with Jellyfin API where searching with apostrophes doesn't work
        if "searchTerm" in params:
            params["searchTerm"] = re.sub(r"['\"’‘”“].*", '', params["searchTerm"])

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                if image_data:
                    response = requests.post(url, headers=headers, params=params, data=image_data)
                else:
                    response = requests.post(url, headers=headers, params=params)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            elif method == "PUT":
                response = requests.put(url, headers=headers, params=params)
            else:
                raise ValueError(f"Invalid method: {method}")

            response.raise_for_status()

            respjson = response.json()
            if isinstance(respjson, dict):
                if respjson.get('TotalRecordCount', 0) >= 1:
                    if "Items" in respjson:
                        return respjson["Items"]
            elif isinstance(respjson, list):
                return respjson

            return []
        except requests.exceptions.RequestException:
            return []

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search(self, query=None, limit=5, path="Items", year=None, parent_id=None, user_id=None,
               include_item_types="Audio",
               recursive=True) -> Optional[list]:
        """
        Search for items in Jellyfin.

        :param query:
        :param limit: amount of items to return
        :param path: api endpoint
        :param year: item year
        :param parent_id:
        :param include_item_types: possible values: Audio, MusicAlbum, MusicArtist (see Jellyfin API docs for more)
        :param recursive:
        :return: list of items if found, otherwise None :class:`Optional[list]`
        """
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
        if user_id:
            params["userId"] = user_id

        return self.request(path, params=params)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search_by_parent_id(self, parent_id, limit=5, include_item_types="Audio", recursive=True) -> Optional[list]:
        """Search for items by parent ID."""
        return self.search(limit=limit, path=f"Items", parent_id=parent_id,
                           include_item_types=include_item_types,
                           recursive=recursive)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search_artist(self, artist_name) -> Optional[dict]:
        """ Search for an artist by name. """
        response = self.search(query=artist_name, include_item_types="MusicArtist")
        for item in response:
            if weighted_word_overlap(item.get('Name', ''), artist_name) > 0.9:
                return item

        return None

    def search_track_for_artist(self, track_name, artist: dict) -> Optional[dict]:
        """
        Search for a track by name for a specific artist. This is useful when the track name is not unique and the
        artist name is known. This is more precise than just searching for the track name.

        :param track_name: Name of the track
        :param artist: Name of the artist
        :return: Track dict if found, otherwise None :class:`Optional[dict]`
        """
        if artist:
            response = self.search_by_parent_id(artist.get('Id'), include_item_types="Audio")
            for item in response:
                if weighted_word_overlap(item.get('Name', ''), track_name) >= 0.66:
                    return item

        return None

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search_album(self, album_name: str, artist_name: str = None) -> Optional[dict]:
        """
        Search for an album by name and will validate with the artist name if provided.

        If no results are found using the provided album name, the album name will be normalized and searched again twice.
        See :func:`self.search_track_by_name` for more information on the normalization process and the why behind it.

        :param album_name: Name of the album :str
        :param artist_name: Name of the artist :str

        :return: Album dict if found, otherwise None :class:`Optional[dict]`
        """
        response = self.search(query=album_name, include_item_types="MusicAlbum")
        if not response:
            album_name = normalize_str(album_name, remove_in_brackets=False, try_fix_track_name=True)
            response = self.search(query=album_name, include_item_types="MusicAlbum")
            if not response:
                album_name = normalize_str(album_name, remove_in_brackets=True, try_fix_track_name=True)
                response = self.search(query=album_name, include_item_types="MusicAlbum")

        for item in response:
            jellyfin_album_name = item.get('Name', '')
            jellyfin_artist_name = format_artists(item.get('Artists', [""]))[0]

            if weighted_word_overlap(jellyfin_album_name, album_name) >= 0.66:
                if not artist_name or weighted_word_overlap(jellyfin_artist_name, artist_name) >= 0.66:
                    return item

        return None

    def search_track_in_album(self, track_name: str, album: dict, duration=None) -> Optional[dict]:
        """
        Search for a track in an album by name and duration (if provided).

        :param track_name: Name of the track :str
        :param album: Album dict from Jellyfin API :dict
        :param duration: Duration of the track in seconds :int

        :return: Track dict if found, otherwise None :class:`Optional[dict]`
        """
        response = self.search_by_parent_id(album.get('Id'))
        for item in response:
            jellyfin_track_name = item.get('Name', '')
            jellyfin_duration = item.get('RunTimeTicks', 0) / 10000000

            if weighted_word_overlap(jellyfin_track_name, track_name) >= 0.66:
                if not duration or close(jellyfin_duration, duration):
                    return item

        return None

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    def search_track_by_name(self, track_name, artist_name=None, album_name=None, duration=None,
                             validate_track_name: bool = True) -> Optional[dict]:
        """
        Search for a track using the name only and then validate the artist name, album name and duration if provided.

        If no results are found using the provided track name, the track name will be normalized and searched again twice:
          1. Will try to fix track name that look like "Song - From ..." to "Song (From ...)". The first format being
          more common in Spotify metadata and the second format being more common in Tidal, in turn in Jellyfin metadata.
          2. Will remove everything that is between parentheses (included) and search again.
        This allows for more flexibility in the search and increases the chances of finding the track.

        If still no results are found, you can disable the track name validation by setting validate_track_name
        to False. This will only validate the artist name, album name and duration if provided.

        :param track_name: The name of the track
        :param artist_name: The name of the artist
        :param album_name: The name of the album
        :param duration: The duration of the track in seconds
        :param validate_track_name: Whether to validate the track name using a ratio method (default: True)

        :return: Track dict if found, otherwise None :class:`Optional[dict]`
        """
        response = self.search(query=track_name, include_item_types="Audio")
        if not response:
            track_name = normalize_str(track_name, remove_in_brackets=False, try_fix_track_name=True)
            response = self.search(query=track_name, include_item_types="Audio")

            if not response:
                track_name = normalize_str(track_name, remove_in_brackets=True, try_fix_track_name=True)
                response = self.search(query=track_name, include_item_types="Audio")

        for item in response:
            jellyfin_track_name = normalize_str(item.get('Name', ''), try_fix_track_name=True)
            jellyfin_artist_name = format_artists(item.get('Artists', [""]))[0]
            jellyfin_album_name = normalize_str(item.get('Album', ''))
            jellyfin_duration = item.get('RunTimeTicks', 0) / 10000000

            if not validate_track_name or weighted_word_overlap(jellyfin_track_name, track_name) >= 0.66:
                if not artist_name or weighted_word_overlap(jellyfin_artist_name, artist_name) >= 0.66:
                    if not album_name or weighted_word_overlap(jellyfin_album_name, album_name) >= 0.66:
                        if not duration or close(jellyfin_duration, duration):
                            return item

        return None

    def does_track_exist(self, track: dict | Track) -> bool:
        """
        Check if a track exists in Jellyfin.

        :param track: Spotify track dict or TidalAPI Track object :class:`tidalapi.Track` :class:`dict`
        :return: True if the track exists, otherwise False :class:`bool`
        """
        return bool(self.get_track_from_data(track))

    def get_track_from_data(self, track: dict | Track) -> Optional[dict]:
        """
        Get Jellyfin track from either a Spotify track dict or a TidalAPI Track object. Using the Tidal Track object
        is more preferable as it contains the same metadata as the files downloaded (with this tool).

        :param track: Spotify track dict or TidalAPI Track object :class:`tidalapi.Track` :class:`dict`
        :return: A Jellyfin track dict if found, otherwise None
        """
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
                return jellyfin_track

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
            return jellyfin_track

        return None

    def compress_metadata_images(self, progress: Progress = None):
        """
        Compresses and resizes images in the metadata directory. This is useful for reducing the size of the metadata
        which can grow quite large with a lot of media. The images are resized to a maximum size defined in the constants
        at the top of this file (default values of Jellyfin).
        The quality of the images is set to 45 which is a good balance between quality and size, especially for images
        that are not viewed in high resolution most of the time.
        In my testing this reduced the size of the metadata directory by ~2/3.

        :param progress: Progress bar to show progress in CLI (optional) :class:`rich.progress.Progress`
        :return: None
        """
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

    @cachebox.cached(cachebox.LRUCache(maxsize=16))
    def get_user_id_from_username(self, username: str) -> Optional[str]:
        """
        Get the user ID from the username.

        :param username: Username of the user :str
        :return: User ID if found, otherwise None :class:`Optional[str]`
        """
        users = self.request("Users")
        for user in users:
            if user.get('Name', '') == username:
                return user.get('Id', '')

        return None

    @cachebox.cached(cachebox.LRUCache(maxsize=16))
    def get_playlists(self, user_id: str) -> list:
        """
        Get the playlists of a user.

        :param user_id: ID of the user :str
        :return: List of playlists :class:`list`
        """

        playlists = self.search("", user_id=user_id, include_item_types="Playlist", limit=500)
        return playlists

    @cachebox.cached(cachebox.LRUCache(maxsize=16))
    def get_playlist_id_from_name(self, playlist_name: str, user_id: str) -> Optional[str]:
        """
        Get the playlist ID from the playlist name.

        :param playlist_name: Name of the playlist :str
        :param user_id: ID of the user :str
        :return: Playlist ID if found, otherwise None :class:`Optional[str]`
        """
        for playlist in self.get_playlists(user_id):
            if playlist.get('Name', '') == playlist_name:
                return playlist.get('Id', '')

        return None

    def create_playlist(self, playlist_name: str, user_id: str, is_public: bool = False, cover_url: str = None):
        playlist_id = self.get_playlist_id_from_name(playlist_name, user_id)
        if playlist_id:
            log.debug(f"Playlist '{playlist_name}' already exists. Deleting and recreating it.")
            self.delete_playlist(playlist_id)

        self.request("Playlists", method="POST", params={
            "Name": playlist_name,
            "MediaType": "Audio",
            "UserId": user_id,
            # "Users": [{"UserId": user, "CanEdit": True} for user in users],
            "IsPublic": is_public
        })

        if cover_url:
            image_data = get_as_base64(cover_url)
            if image_data:
                playlist_id = self.get_playlist_id_from_name(playlist_name, user_id)
                self.request(f"Items/{playlist_id}/Images/Primary", method="POST", image_data=image_data)

    def delete_playlist(self, playlist_id: str):
        self.request(f"Items/{playlist_id}", method="DELETE")

    def add_track_to_playlist(self, track_id: str, playlist_id: str, user_id: str):
        params = {
            "ids": track_id,
            "userId": user_id
        }

        self.request(f"Playlists/{playlist_id}/Items", method="POST", params=params)

    def add_tracks_to_playlist(self, track_ids: list, playlist_id: str, user_id: str):
        # Split the list of track IDs into chunks of 10
        for i in range(0, len(track_ids), 10):
            # Get a chunk of 10 (or less, if it's the last group)
            batch = track_ids[i:i + 10]
            # Add the tracks to the playlist as a comma-separated string
            self.add_track_to_playlist(",".join(batch), playlist_id, user_id)

    def sync_playlist(self, playlist_with_tracks: dict, user: str, progress: Progress = None):
        user = self.get_user_id_from_username(user)
        if not user:
            log.error(f"User '{user}' not found.")
            return

        tracks_id_to_add = []

        # Check if the playlist is the Liked Songs playlist or a regular playlist
        if isinstance(playlist_with_tracks, list):
            # Liked Songs playlist
            playlist_name = "Liked Songs"
            self.create_playlist(playlist_name, user, is_public=False,
                                 cover_url="https://misc.scdn.co/liked-songs/liked-songs-300.png")

            for track in playlist_with_tracks:
                track = track.get('track')
                jellyfin_track = self.get_track_from_data(track)
                if jellyfin_track:
                    tracks_id_to_add.append(jellyfin_track.get('Id', ''))

        # Regular playlist
        elif isinstance(playlist_with_tracks, dict):
            playlist_name = playlist_with_tracks.get('name', '')
            tracks = playlist_with_tracks.get('tracks', [])
            author = playlist_with_tracks.get('owner', {}).get('id', '')
            is_public = author == "spotify"
            cover_url = playlist_with_tracks.get('images', [{}])[0].get('url', None)

            self.create_playlist(playlist_name, user, is_public, cover_url)

            for track in tracks:
                track = track.get('track')
                jellyfin_track = self.get_track_from_data(track)
                if jellyfin_track:
                    tracks_id_to_add.append(jellyfin_track.get('Id', ''))

        # Add the tracks to the playlist
        if tracks_id_to_add and playlist_name:
            self.add_tracks_to_playlist(tracks_id_to_add, self.get_playlist_id_from_name(playlist_name, user), user)
