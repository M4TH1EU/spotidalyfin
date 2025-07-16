import json
import logging
from json import JSONDecodeError
from typing import Optional, List, cast

import tidalapi
from tidalapi import media
from tidalapi.exceptions import ObjectNotFound
from tidalapi.media import Lyrics
from tidalapi.session import SearchResults

from spotidalyfin.db.database import Database
from spotidalyfin.db.helpers import get_authenticated_tidal_profiles, save_tidal_info_to_db, get_tidal_login_info
from spotidalyfin.models import Track, TrackQuality
from spotidalyfin.models.album import TidalAlbum
from spotidalyfin.models.artist import TidalArtist
from spotidalyfin.models.enums import Platform
from spotidalyfin.models.manager import Manager
from spotidalyfin.models.playlist import Playlist, TidalFavoriteTracksPlaylist, \
    TidalPlaylist
from spotidalyfin.models.track import TidalTrack


def _parse_real_track_quality(track: tidalapi.Track) -> TrackQuality:
    """The audio_quality parameter isn't always correct"""
    if track.is_dolby_atmos:
        return TrackQuality.DOLBY_ATMOS
    elif track.is_hi_res_lossless:
        return TrackQuality.HI_RES_LOSSLESS
    elif track.is_lossless:
        return TrackQuality.LOSSLESS
    else:
        return TrackQuality.LOW


def _parse_track(tidal_track: tidalapi.Track) -> TidalTrack:
    return TidalTrack(
        name=tidal_track.name,
        id=str(tidal_track.id),
        artist=_parse_artist(tidal_track.artist) if tidal_track.artist else None,
        album=_parse_album(tidal_track.album) if tidal_track.album else None,
        duration=tidal_track.duration,
        quality=_parse_real_track_quality(tidal_track),
        isrc=tidal_track.isrc.upper()
    )


def _parse_artist(tidal_artist: tidalapi.Artist) -> TidalArtist:
    return TidalArtist(
        name=tidal_artist.name,
        id=str(tidal_artist.id),
        image=tidal_artist.picture
    )


def _parse_album(tidal_album: tidalapi.Album, fetch_tracks: bool = False) -> TidalAlbum:
    return TidalAlbum(
        name=tidal_album.name,
        id=str(tidal_album.id),
        artist=_parse_artist(tidal_album.artist) if tidal_album.artist else None,
        barcode=tidal_album.upc,
        release_date=tidal_album.release_date,
        cover_url=tidal_album.cover,
        tracks=tidal_album.tracks() if fetch_tracks else None,
    )


def _parse_playlist(tidal_playlist: tidalapi.Playlist, fetch_tracks: bool = False) -> TidalPlaylist:
    return TidalPlaylist(
        name=tidal_playlist.name,
        id=tidal_playlist.id,
        image=tidal_playlist.image(640),
        tracks=_fetch_playlist_tracks(tidal_playlist) if fetch_tracks else None,
    )


def _parse_favorites_tracks(tidal_playlist: tidalapi.Playlist) -> TidalFavoriteTracksPlaylist:
    """Parse TIDAL's favorite tracks playlist."""
    return TidalFavoriteTracksPlaylist(
        name="Favorite Tracks",
        tracks=_fetch_playlist_tracks(tidal_playlist)
    )


def _fetch_playlist_tracks(tidal_playlist: tidalapi.Playlist) -> List[Track]:
    """Fetch tracks from a TIDAL playlist."""
    total = tidal_playlist.num_tracks
    tracks = []
    for offset in range(0, total, 100):
        tracks.extend(_parse_track(track) for track in tidal_playlist.tracks(offset=offset, limit=100))

    return tracks


def create_temp_session_tidal(config: tidalapi.Config = tidalapi.Config()) -> tidalapi.Session:
    """Get the URL for logging in with TIDAL using PKCE flow."""
    return tidalapi.Session(config=config)


def login_tidal(session: tidalapi.Session(), response_url: str, db: Database = None) -> (bool, str):
    """Try to authenticate with TIDAL using the given redirect URL. Optionally save the account into the database."""
    try:
        response: dict = session.pkce_get_auth_token(response_url)
        if db and "user" in response:
            if response.get("user").get("username") in get_authenticated_tidal_profiles(db):
                return False, "This account is already authenticated, please remove it and try again."

            save_tidal_info_to_db(db, response)

        return True, ""
    except Exception as e:
        logging.exception("Failed to authenticate with TIDAL")

        try:
            error = json.loads(e.response.content.decode()).get("error_description")
            if error:
                return False, f"Failed to authenticate with TIDAL: {error}"
        except JSONDecodeError | TypeError:
            logging.exception("Failed to parse TIDAL authentication error response")
            return False, f"Failed to authenticate with TIDAL. Please try again."


class TidalManager(Manager):
    PLATFORM = Platform.TIDAL

    def __init__(self, username: str, db: Database):
        self.username = username
        self.db = db

        # Initialize TIDAL session
        self.client = tidalapi.Session()
        login_info = get_tidal_login_info(db, username)
        self.client.load_oauth_session(access_token=login_info[0], refresh_token=login_info[1], token_type="Bearer",
                                       is_pkce=True)
        self.client.audio_quality = TrackQuality.HI_RES_LOSSLESS.name  # TODO: allow configuration
        self.db = db

    def get_track(self, track_id: str) -> Optional[TidalTrack]:
        try:
            tidal_track = self.client.track(track_id)
            if tidal_track:
                return _parse_track(tidal_track)
        except ObjectNotFound as e:
            logging.exception(f"Failed to fetch TIDAL track with ID {track_id}: {e}")
            return None

    def get_album(self, album_id: str) -> Optional[TidalAlbum]:
        try:
            tidal_album = self.client.album(album_id)
            if tidal_album:
                return _parse_album(tidal_album, fetch_tracks=True)
        except ObjectNotFound as e:
            logging.exception(f"Failed to fetch TIDAL album with ID {album_id}: {e}")
            return None

    def get_artist(self, artist_id: str) -> Optional[TidalArtist]:
        try:
            tidal_artist = self.client.artist(artist_id)
            if tidal_artist:
                return _parse_artist(tidal_artist)
        except ObjectNotFound as e:
            logging.exception(f"Failed to fetch TIDAL artist with ID {artist_id}: {e}")
            return None

    def get_playlist(self, playlist_id: str, fetch_tracks: bool = False, fetch_albums: bool = False) -> Optional[
        TidalPlaylist]:
        if playlist_id == "favorite_tracks":
            return self.get_favorite_tracks()

        try:
            tidal_playlist = self.client.playlist(playlist_id)
            if tidal_playlist:
                return _parse_playlist(tidal_playlist, fetch_tracks=fetch_tracks)
        except ObjectNotFound as e:
            logging.exception(f"Failed to fetch TIDAL playlist with ID {playlist_id}: {e}")
            return None

    def get_user_playlists(self, user_id: str = None, fetch_tracks: bool = False) -> list[TidalPlaylist]:
        """Retrieve all playlists for a user."""
        try:
            if not user_id:
                playlists = self.client.user.playlists()
            else:
                playlists = self.client.get_user(int(user_id)).playlists()

            return [_parse_playlist(playlist, fetch_tracks) for playlist in playlists]
        except Exception as e:
            logging.exception(f"Failed to fetch TIDAL playlists for user {user_id}: {e}")
            return []

    def get_favorite_tracks(self) -> Optional[TidalFavoriteTracksPlaylist]:
        try:
            liked_songs = self.client.user.favorites(limit=100, offset=0)
            total = liked_songs.total
            tracks = liked_songs.items

            for offset in range(0, total, 100):
                liked_songs = self.client.user.favorites(limit=100, offset=offset)
                if not liked_songs.items:
                    break

                tracks.extend(liked_songs.items)

            return TidalFavoriteTracksPlaylist(
                name="Liked Songs",
                tracks=[_parse_track(track) for track in tracks]
            )
        except Exception as e:
            logging.exception("Failed to fetch favorite tracks from TIDAL")
            return None

    def _search(self,
                query: str,
                models: Optional[List[tidalapi.Album or tidalapi.Track or tidalapi.Artist]] = None,
                limit: int = 7
                ) -> Optional[SearchResults]:
        """
        Performs a search on TIDAL with the given query and models.

        :param query: The search query string.
        :param models: A list of models to search for (default: Track, available: Track, Album, Artist).
        :param limit: Maximum number of results to return (default: 7).

        :return: Search results.
        """
        try:
            sanitized_query = query[:99]  # Ensure query length does not exceed TIDAL limits
            models = models or [media.Track]
            return self.client.search(sanitized_query, limit=limit, models=models)
        except Exception as e:
            logging.exception(f"Failed to search TIDAL with query '{query}': {e}")
            return None

    def search_tracks_by_query(self, query: str) -> list[TidalTrack]:
        try:
            search_results = self._search(query, models=[media.Track])
            if not search_results or not search_results.get('tracks'):
                return []

            return [_parse_track(track) for track in search_results.get('tracks', [])]
        except Exception as e:
            logging.exception(f"Failed to search TIDAL tracks with query '{query}': {e}")
            return []

    def search_tracks_by_isrc(self, isrc: str) -> list[TidalTrack]:
        try:
            tracks = self.client.get_tracks_by_isrc(isrc)
            return [_parse_track(track) for track in tracks] if tracks else []

        except Exception as e:
            logging.exception(f"Failed to search TIDAL tracks with ISRC '{isrc}': {e}")
            return []

    def search_albums_by_query(self, query: str) -> list[TidalAlbum]:
        try:
            search_results = self._search(query, models=[media.Album])
            if not search_results or not search_results.get('albums'):
                return []

            return [_parse_album(album) for album in search_results.get('albums', [])]
        except Exception as e:
            logging.exception(f"Failed to search TIDAL albums with query '{query}': {e}")
            return []

    def search_albums_by_upc(self, upc: str) -> list[TidalAlbum]:
        try:
            albums = self.client.get_albums_by_barcode(upc)
            return [_parse_album(album) for album in albums] if albums else []

        except Exception as e:
            logging.exception(f"Failed to search TIDAL albums with UPC '{upc}': {e}")
            return []

    def search_artists(self, query: str) -> list[TidalArtist]:
        try:
            search_results = self._search(query, models=[tidalapi.Artist])
            if not search_results or not search_results.get('artists'):
                return []

            return [_parse_artist(artist) for artist in search_results.get('artists', [])]
        except Exception as e:
            logging.exception(f"Failed to search TIDAL artists with query '{query}': {e}")
            return []

    def supports_lyrics(self) -> bool:
        return True

    def get_lyrics(self, track: TidalTrack) -> str:
        try:
            request = self.client.request.request("GET", "tracks/%s/lyrics" % track.id)
            json_obj = request.json()
            lyrics = self.client.request.map_json(json_obj, parse=Lyrics().parse)
            assert not isinstance(lyrics, list)

            lyrics = cast("Lyrics", lyrics)
            return lyrics.subtitles or lyrics.text
        except ObjectNotFound | Exception:
            logging.exception(f"Lyrics not found for track {track.name} by {track.artist.name}")
            return ""

    def create_empty_playlist(self, name: str, description: str = "", cover_url: str = "") -> Optional[TidalPlaylist]:
        try:
            new_playlist = self.client.user.create_playlist(title=name, description=description)
            # TODO: Handle cover
            return _parse_playlist(new_playlist, fetch_tracks=False)
        except Exception as e:
            logging.exception(f"Failed to create TIDAL playlist '{name}': {e}")
            return None

    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[Track]) -> bool:
        try:
            tidal_playlist = self.client.playlist(playlist.id)

            for i in range(0, len(tracks), 100):
                tidal_playlist.add([track.id for track in tracks[i:i + 100]])

            return True

        except Exception as e:
            logging.exception(f"Failed to add tracks to TIDAL playlist '{playlist.id}': {e}")
            return False

    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        try:
            tidal_playlist = self.client.playlist(playlist_id)
            tidal_playlist.delete()
            return True
        except ObjectNotFound as e:
            logging.exception(f"Playlist with ID {playlist_id} not found: {e}")
            return False
        except Exception as e:
            logging.exception(f"Failed to remove TIDAL playlist with ID {playlist_id}: {e}")
            return False

# OLD CODE TO MIGRATE

# tidal_search = self.search_tracks(track_name=spotify_track.name, artist_name=spotify_track.artist.name,
#                                   isrc=spotify_track.isrc, retrieve_streams=retrieve_streams)
# list_of_matches: list[Track] = []
# for tidal_track in tidal_search:
#     match, score = spotify_track.matches(other=tidal_track)
#
#     if match:
#         list_of_matches.append(tidal_track)
#
# if not list_of_matches:
#     raise TrackNotFoundException(
#         f"No matches found on TIDAL for track {spotify_track.name} - {spotify_track.artist.name}")
#
# list_of_matches.sort(key=lambda x: x.quality.value + x.score, reverse=True)
# save_match(self.db, spotify_track.track_id, list_of_matches[0].track_id)
# return list_of_matches[0]


# def download_track(self,
#                    track: Track,
#                    quality: TrackQuality = TrackQuality.HI_RES_LOSSLESS,
#                    output_type: str = "flac",
#                    destination: str = "~/Music/Spotidalyfin",
#                    lyrics: bool = True
#                    ):
#     """
#     Downloads a track to the given destination.
#
#     :param track: The track to download.
#     :param quality: The quality of the downloaded track.
#     :param output_type: The output file type.
#     :param destination: The destination folder.
#     :param lyrics: Whether to download the lyrics. Slows down the process a bit.
#
#     :raises DownloadTrackException: If the track cannot be downloaded.
#     """
#
#     try:
#         if quality:
#             self.client.audio_quality = quality.name
#
#         if destination:
#             destination = Path(destination).expanduser()
#
#         raw_data, filetype = track.raw_data()
#
#         if filetype == "m4a" and output_type == "flac":
#             raw_data = convert_m4a_bytes_to_flac(raw_data)
#             filetype = "flac"
#
#         if lyrics:
#             track.lyrics = self.get_lyrics(track)
#
#         metadata = track.metadata()
#         out_file = metadata.generate_path(base_path=destination, extension=filetype)
#         out_file.parent.mkdir(parents=True, exist_ok=True)
#
#         with open(out_file, "wb") as f:
#             f.write(raw_data)
#
#         metadata.write_to_file(out_file)
#     except Exception as e:
#         raise DownloadTrackException(f"Failed to download track {track.name} - {track.artist.name}: {e}") from e
#
# def download_playlist(self,
#                       playlist: Playlist,
#                       quality: TrackQuality = TrackQuality.HI_RES_LOSSLESS,
#                       output_type: str = "flac",
#                       destination: str = "~/Music/Spotidalyfin",
#                       status_container: StatusContainer = None,
#                       progress_bar: ProgressMixin = None
#                       ) -> List[tuple[bool, Track]]:
#     """
#     Downloads a playlist to the given destination.
#
#     :param playlist: The playlist to download.
#     :param quality: The quality of the downloaded tracks.
#     :param output_type: The output file type.
#     :param destination: The destination folder.
#     :param status_container: The status container to update, if any.
#     :param progress_bar: A Streamlit progress bar widget.
#
#     :raises DownloadPlaylistException:
#
#     :return: A list of tuples containing the download status and the track.
#     """
#
#     if quality:
#         self.client.audio_quality = quality.name
#
#     if destination:
#         destination = Path(destination).expanduser()
#
#     # Total number of tracks to download
#     total_tracks = len(playlist.tracks)
#
#     # Initialize the progress bar
#     if progress_bar is not None:
#         progress_bar.progress(0, "Downloading tracks...")
#
#     # Track progress in the main thread using a shared variable
#     def _execute_download(_track, _progress_tracker, attempts=0):
#         if not "streamlit_script_run_ctx" in threading.current_thread().__dict__:
#             if attempts < 10:
#                 time.sleep(0.1)
#                 attempts += 1
#                 return _execute_download(_track, _progress_tracker, attempts)
#             else:
#                 raise DownloadPlaylistException("Failed to download track due to missing script run context.")
#
#         # Create an st.empty() container to write status messages (no spamming logs)
#         track_empty = status_container.empty() if status_container else None
#
#         try:
#             if track_empty:
#                 track_empty.write(f"*-> Downloading track: {_track.name}*")
#
#             self.download_track(_track, quality, output_type, destination)
#
#             # Update progress in the main thread safely
#             if progress_bar is not None:
#                 _progress_tracker[0] += 1
#                 progress_bar.progress(_progress_tracker[0] / total_tracks,
#                                       f"{_progress_tracker[0]}/{total_tracks} tracks downloaded")
#
#             if track_empty:
#                 track_empty.write(f"*:green[-> Downloaded track: {_track.name}]*")
#
#             return True, _track
#
#         except Exception as e:
#             log.exception(f"Failed to download track {_track.name} in playlist {playlist.name}")
#             if track_empty:
#                 track_empty.write(f"**:red[-> {e}]**")
#
#             return False, _track
#
#     # Shared progress tracker (using list to ensure it's mutable)
#     progress_tracker = [0]
#
#     summary_downloads = []
#
#     # Use ThreadPoolExecutor to download tracks in parallel
#     with ThreadPoolExecutor(max_workers=4) as executor:
#         results = executor.map(lambda track: _execute_download(track, progress_tracker), playlist.tracks)
#
#         for t in executor._threads:
#             add_script_run_ctx(t)
#
#         for result in results:
#             summary_downloads.append(result)
#
#     return summary_downloads
