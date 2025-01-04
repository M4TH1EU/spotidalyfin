import json
import threading
import time
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

import cachebox
import tidalapi
from streamlit.elements.lib.mutable_status_container import StatusContainer
from streamlit.elements.progress import ProgressMixin
from streamlit.runtime.scriptrunner_utils.script_run_context import add_script_run_ctx
from tidalapi import media
from tidalapi.exceptions import ObjectNotFound
from tidalapi.session import SearchResults

from spotidalyfin import cfg
from spotidalyfin.db.database import Database
from spotidalyfin.db.helpers import save_tidal_info_to_db, get_tidal_login_info, get_authenticated_tidal_profiles
from spotidalyfin.managers import types
from spotidalyfin.managers.types import Track, Album, Artist, TrackQuality, Playlist, Platform
from spotidalyfin.utils.decorators import rate_limit
from spotidalyfin.utils.file_utils import convert_m4a_bytes_to_flac


def create_temporary_session(config: tidalapi.Config = tidalapi.Config()) -> tidalapi.Session:
    """Get the URL for logging in with TIDAL using PKCE flow."""
    return tidalapi.Session(config=config)


def try_to_authenticate_with_tidal(session: tidalapi.Session(), redirect_url: str, db: Database = None) -> (bool, str):
    """Try to authenticate with TIDAL using the given redirect URL. Optionally save the account into the database."""
    try:
        response: dict = session.pkce_get_auth_token(redirect_url)
        if db and "user" in response:
            if response.get("user").get("username") in get_authenticated_tidal_profiles(db):
                return False, "This account is already authenticated, please remove it and try again."

            save_tidal_info_to_db(db, response)

        return True, ""
    except Exception as e:
        try:
            error = json.loads(e.response.content.decode()).get("error_description")
            if error:
                return False, f"Failed to authenticate with TIDAL: {error}"
        except Exception:
            pass

    return False, f"Failed to authenticate with TIDAL. Please try again."


class TidalManager:
    """
    A manager for interacting with the TIDAL API, handling track, album, and artist retrievals,
    and supporting search functionality.
    """

    def __init__(self, username: str, db: Database) -> None:
        """
        Initializes the TIDAL manager, ensuring session setup and audio quality configuration.
        """
        session_file = cfg.get("config-dir") / "tidal-session-pkce.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        self.client = tidalapi.Session()
        login_info = get_tidal_login_info(db, username)
        self.client.load_oauth_session(access_token=login_info[0], refresh_token=login_info[1], token_type="Bearer",
                                       is_pkce=True)
        self.client.audio_quality = TrackQuality.HI_RES_LOSSLESS.name  # TODO: allow configuration

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_track(self, track_id: str) -> Track:
        """
        Retrieves a track by its ID.

        :param track_id: The ID of the track to retrieve.
        :return: A Track object.
        :raises ValueError: If the track cannot be found.
        """
        try:
            tidal_track = self.client.track(track_id)
            return types.track_from_tidal_track(tidal_track)
        except ObjectNotFound:
            raise ValueError(f"Failed to fetch track with ID {track_id}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_album(self, album_id: str, load_tracks: bool = False) -> Album:
        """
        Retrieves an album by its ID.

        :param album_id: The ID of the album to retrieve.
        :param load_tracks: Whether to load the album's tracks.
        :return: An Album object.
        :raises ValueError: If the album cannot be found.
        """
        try:
            tidal_album = self.client.album(album_id)
            return types.album_from_tidal_album(tidal_album, load_tracks)
        except ObjectNotFound:
            raise ValueError(f"Failed to fetch album with ID {album_id}")

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def get_artist(self, artist_id: str) -> Artist:
        """
        Retrieves an artist by their ID.

        :param artist_id: The ID of the artist to retrieve.
        :return: An Artist object.
        :raises ValueError: If the artist cannot be found.
        """
        try:
            tidal_artist = self.client.artist(artist_id)
            return types.artist_from_tidal_artist(tidal_artist)
        except ObjectNotFound:
            raise ValueError(f"Failed to fetch artist with ID {artist_id}")

    @rate_limit
    def search(
            self,
            query: str,
            models: Optional[List[tidalapi.Album or tidalapi.Track or tidalapi.Artist]] = None,
            limit: int = 7
    ) -> SearchResults:
        """
        Performs a search on TIDAL with the given query and models.

        :param query: The search query string.
        :param models: A list of models to search for (default: Track, available: Track, Album, Artist).
        :param limit: Maximum number of results to return (default: 7).
        :return: Search results.
        """
        sanitized_query = query[:99]  # Ensure query length does not exceed TIDAL limits
        models = models or [media.Track]
        return self.client.search(sanitized_query, limit=limit, models=models)

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def search_artists(self, artist_name: str) -> List[Artist]:
        """
        Searches for artists by name.

        :param artist_name: The name of the artist to search for.
        :return: A list of Artist objects.
        """
        artists = self.search(artist_name, models=[tidalapi.Artist]).get('artists', [])
        return [types.artist_from_tidal_artist(artist) for artist in artists]

    @cachebox.cached(cachebox.LRUCache(maxsize=256))
    @rate_limit
    def search_albums(
            self,
            album_name: Optional[str] = "",
            artist_name: Optional[str] = "",
            barcode: Optional[str] = None
    ) -> List[Album]:
        """
        Searches for albums by name, artist name, or barcode.

        :param album_name: The name of the album to search for.
        :param artist_name: The name of the album's artist.
        :param barcode: The barcode of the album.
        :return: A list of Album objects.
        """
        try:
            albums = []

            if barcode:
                albums = self.client.get_albums_by_barcode(barcode)

            if not albums and (album_name or artist_name):
                albums = self.search(f"{album_name} {artist_name}", models=[tidalapi.Album]).get('albums', [])

            return [types.album_from_tidal_album(album) for album in albums]
        except (ObjectNotFound, KeyError):
            return []

    @cachebox.cached(cachebox.LRUCache(maxsize=128))
    @rate_limit
    def search_tracks(
            self,
            track_name: Optional[str] = "",
            artist_name: Optional[str] = "",
            isrc: Optional[str] = None
    ) -> List[Track]:
        """
        Searches for tracks by name, artist name, or ISRC code.

        :param track_name: The name of the track to search for.
        :param artist_name: The name of the track's artist.
        :param isrc: The ISRC code of the track.
        :return: A list of Track objects.
        """
        try:
            tracks = []

            # First search by ISRC
            if isrc:
                tracks = self.client.get_tracks_by_isrc(isrc.upper())

            # If no results, search by track name and artist name
            if not tracks and (track_name or artist_name):
                tracks = self.search(f"{track_name} {artist_name}").get('tracks', [])

            return [types.track_from_tidal_track(track) for track in tracks]
        except (ObjectNotFound, KeyError):
            return []

    def convert_spotify_track(self, spotify_track: Track) -> Optional[Track]:
        """
        Converts a Spotify track to a TIDAL track.

        :param spotify_track: The Spotify track to convert.
        :return: A TIDAL track.
        """
        tidal_search = self.search_tracks(track_name=spotify_track.name, artist_name=spotify_track.artist.name,
                                          isrc=spotify_track.isrc)
        list_of_matches: list[Track] = []
        for tidal_track in tidal_search:
            match, score = spotify_track.matches(other=tidal_track)

            if match:
                list_of_matches.append(tidal_track)

        if not list_of_matches:
            return None

        list_of_matches.sort(key=lambda x: x.quality.value + x.score, reverse=True)
        return list_of_matches[0]

    def convert_spotify_playlist(self, spotify_playlist: Playlist,
                                 status_container: StatusContainer = None) -> Playlist:
        """
        Converts a Spotify playlist to a TIDAL playlist.

        :param spotify_playlist: The Spotify playlist to convert.
        :param status_container: The streamlit status container to update, if any.

        :return: A TIDAL playlist.
        """
        tidal_playlist = Playlist(
            platform=Platform.TIDAL,
            name=spotify_playlist.name,
            image=spotify_playlist.image,
            playlist_id=spotify_playlist.playlist_id
        )

        for spotify_track in spotify_playlist.tracks:
            if status_container:
                status_container.write(f"*-> Matching track: {spotify_track.name} - {spotify_track.artist.name}*")

            tidal_track = self.convert_spotify_track(spotify_track)
            if tidal_track:
                tidal_playlist.tracks.append(tidal_track)
            else:
                if status_container:
                    status_container.write(f"Failed to match track: {spotify_track.name} - {spotify_track.artist.name}")
                pass  # TODO: handle unmatched tracks

        return tidal_playlist

    def download_track(self,
                       track: Track,
                       quality: TrackQuality = TrackQuality.HI_RES_LOSSLESS,
                       output_type: str = "flac",
                       destination: str = "~/Music/Spotidalyfin"
                       ):
        """
        Downloads a track to the given destination.

        :param track: The track to download.
        :param quality: The quality of the downloaded track.
        :param output_type: The output file type.
        :param destination: The destination folder.
        """

        try:
            if quality:
                self.client.audio_quality = quality.name

            if destination:
                destination = Path(destination).expanduser()

            raw_data, filetype = track.raw_data()

            if filetype == "m4a" and output_type == "flac":
                raw_data = convert_m4a_bytes_to_flac(raw_data)
                filetype = "flac"

            metadata = track.metadata()
            out_file = metadata.generate_path(base_path=destination, extension=filetype)
            out_file.parent.mkdir(parents=True, exist_ok=True)

            with open(out_file, "wb") as f:
                f.write(raw_data)

            metadata.write_to_file(out_file)
        except Exception as e:
            raise ValueError(f"Failed to download track {track.name}: {e}")

    ### OLD BUT GOLD (WORKS)
    def download_playlist(self,
                          playlist: Playlist,
                          quality: TrackQuality = TrackQuality.HI_RES_LOSSLESS,
                          output_type: str = "flac",
                          destination: str = "~/Music/Spotidalyfin",
                          status_container: StatusContainer = None,
                          progress_bar: ProgressMixin = None
                          ):
        """
        Downloads a playlist to the given destination.

        :param playlist: The playlist to download.
        :param quality: The quality of the downloaded tracks.
        :param output_type: The output file type.
        :param destination: The destination folder.
        :param status_container: The status container to update, if any.
        :param progress_bar: A Streamlit progress bar widget.
        """

        if quality:
            self.client.audio_quality = quality.name

        if destination:
            destination = Path(destination).expanduser()

        # Total number of tracks to download
        total_tracks = len(playlist.tracks)

        # Initialize the progress bar
        if progress_bar is not None:
            progress_bar.progress(0)

        # Track progress in the main thread using a shared variable
        def _execute_download(_track, _progress_tracker, attempts=0):
            if not "streamlit_script_run_ctx" in threading.current_thread().__dict__:
                if attempts < 10:
                    time.sleep(0.1)
                    attempts += 1
                    return _execute_download(_track, _progress_tracker, attempts)
                else:
                    raise ValueError("Failed to download track due to missing script run context.")

            # Create an st.empty() container to write status messages (no spamming logs)
            track_empty = status_container.empty() if status_container else None

            try:
                if track_empty:
                    track_empty.write(f"*-> Downloading track: {_track.name}*")

                self.download_track(_track, quality, output_type, destination)

                # Update progress in the main thread safely
                if progress_bar is not None:
                    _progress_tracker[0] += 1
                    progress_bar.progress(_progress_tracker[0] / total_tracks)

                if track_empty:
                    track_empty.write(f"*:green[-> Downloaded track: {_track.name}]*")

            except Exception as e:
                if track_empty:
                    track_empty.write(f"**:red[-> {e}]**")
                raise ValueError(e)

        # Shared progress tracker (using list to ensure it's mutable)
        progress_tracker = [0]

        # Use ThreadPoolExecutor to download tracks in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = executor.map(lambda track: _execute_download(track, progress_tracker), playlist.tracks)

            for t in executor._threads:
                add_script_run_ctx(t)

            for result in results:
                pass

    # #### LOOKS NICE BUT MISSING SCRIPT CONTEXT STILL
    # def download_playlist(
    #         self,
    #         playlist: Playlist,
    #         quality: TrackQuality = TrackQuality.HI_RES_LOSSLESS,
    #         output_type: str = "flac",
    #         destination: str = "~/Music/Spotidalyfin",
    #         status_container=None,
    #         progress_bar=None
    # ):
    #     """Downloads a playlist to the given destination."""
    #     # Setup
    #     self.client.audio_quality = quality.name if quality else None
    #     dest_path = str(Path(destination).expanduser())
    #     total_tracks = len(playlist.tracks)
    #     progress = [0]  # Mutable counter for tracking progress
    #
    #     if progress_bar:
    #         progress_bar.progress(0)
    #
    #     def _execute_download(track):
    #         # Ensure Streamlit context exists
    #         for _ in range(10):
    #             if "streamlit_script_run_ctx" in threading.current_thread().__dict__:
    #                 break
    #             time.sleep(0.1)
    #         else:
    #             raise ValueError("Missing script run context")
    #
    #         try:
    #             # Update status and download
    #             track_log_text = status_container.empty() if status_container else None
    #             if track_log_text:
    #                 track_log_text.write(f"*-> Downloading: {track.name}*")
    #
    #             self.download_track(track, quality, output_type, dest_path)
    #
    #             # Update progress
    #             if progress_bar:
    #                 progress[0] += 1
    #                 progress_bar.progress(progress[0] / total_tracks)
    #
    #             if track_log_text:
    #                 track_log_text.write(f"*:green[✓ {track.name}]*")
    #
    #         except Exception as e:
    #             if track_log_text:
    #                 track_log_text.write(f"**:red[Error: {e}]**")
    #             raise
    #
    #     # Download tracks in parallel
    #     with ThreadPoolExecutor(max_workers=1) as executor:
    #         executor.map(lambda track: _execute_download(track), playlist.tracks)
    #         for t in executor._threads:
    #             add_script_run_ctx(t)
