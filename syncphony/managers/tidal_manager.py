import tempfile
from pathlib import Path
from typing import Optional, List, cast

import requests
import tidalapi
from sqlmodel import Session, select
from tidalapi import media
from tidalapi.exceptions import ObjectNotFound, TooManyRequests
from tidalapi.media import Lyrics, Stream, AudioExtensions, StreamManifest
from tidalapi.session import SearchResults

from syncphony.db.models import TidalAccount
from syncphony.types import Track, TrackQuality
from syncphony.types.album import TidalAlbum
from syncphony.types.artist import TidalArtist
from syncphony.types.enums import Platform
from syncphony.types.manager import Manager
from syncphony.types.playlist import Playlist, TidalFavoriteTracksPlaylist, \
    TidalPlaylist
from syncphony.types.track import TidalTrack
from syncphony.utils.decorators import rate_limit
from syncphony.utils.download import download_all_ordered
from syncphony.utils.ffmpeg import convert_m4a_bytes_to_flac
from syncphony.utils.files import generate_path
from syncphony.utils.logger import log
from syncphony.utils.metadata import process_metadata


def _get_tidal_quality(quality: TrackQuality) -> str:
    if quality == TrackQuality.DOLBY_ATMOS:
        return "DOLBY_ATMOS"
    elif quality == TrackQuality.EXTREME:
        return "HI_RES_LOSSLESS"
    elif quality == TrackQuality.HIGH:
        return "LOSSLESS"
    elif quality == TrackQuality.MEDIUM:
        return "HIGH"
    else:
        return "LOW"


def _parse_real_track_quality(track: tidalapi.Track) -> TrackQuality:
    """The audio_quality parameter isn't always correct"""
    if track.is_dolby_atmos:
        return TrackQuality.DOLBY_ATMOS
    elif track.is_hi_res_lossless:
        return TrackQuality.EXTREME
    elif track.is_lossless:
        return TrackQuality.HIGH
    elif track.audio_quality == "HIGH":
        return TrackQuality.MEDIUM
    else:
        return TrackQuality.LOW


def _parse_track(tidal_track: tidalapi.Track, fetch_album_tracks: bool = False) -> TidalTrack:
    return TidalTrack(
        name=tidal_track.name,
        id=str(tidal_track.id),
        artist=_parse_artist(tidal_track.artist) if tidal_track.artist else None,
        album=_parse_album(tidal_track.album, fetch_album_tracks) if tidal_track.album else None,
        duration=tidal_track.duration,
        quality=_parse_real_track_quality(tidal_track),
        isrc=tidal_track.isrc.upper(),
        replay_gain=tidal_track.replay_gain,
        replay_peak=tidal_track.peak,
        track_number=tidal_track.track_num,
        vol_number=tidal_track.volume_num
    )


def _parse_artist(tidal_artist: tidalapi.Artist) -> TidalArtist:
    return TidalArtist(
        name=tidal_artist.name,
        id=str(tidal_artist.id),
        image=tidal_artist.picture
    )


def _parse_album(tidal_album: tidalapi.Album, fetch_album_tracks: bool = False) -> TidalAlbum:
    return TidalAlbum(
        name=tidal_album.name,
        id=str(tidal_album.id),
        artist=_parse_artist(tidal_album.artist) if tidal_album.artist else None,
        barcode=tidal_album.upc,
        release_date=tidal_album.release_date,
        # cover=get_as_base64(f"https://resources.tidal.com/images/{tidal_album.cover.replace('-', '/')}/1280x1280.jpg"),
        tracks=[_parse_track(track) for track in tidal_album.tracks()] if fetch_album_tracks else None,
        num_volumes=tidal_album.num_volumes,
        num_tracks=tidal_album.num_tracks,
        duration=tidal_album.duration,
        copyright=tidal_album.copyright
    )


def _parse_playlist(tidal_playlist: tidalapi.Playlist, fetch_tracks: bool = False,
                    fetch_albums: bool = False, fetch_albums_tracks: bool = False) -> TidalPlaylist:
    return TidalPlaylist(
        name=tidal_playlist.name,
        id=tidal_playlist.id,
        # image=get_as_base64(tidal_playlist.image(640)),
        tracks=_fetch_playlist_tracks(tidal_playlist, fetch_albums, fetch_albums_tracks) if fetch_tracks else None,
    )


def _parse_favorites_tracks(tidal_playlist: tidalapi.Playlist) -> TidalFavoriteTracksPlaylist:
    """Parse TIDAL's favorite tracks playlist."""
    return TidalFavoriteTracksPlaylist(
        name="Favorite Tracks",
        tracks=_fetch_playlist_tracks(tidal_playlist)
    )


@rate_limit(returns=[])
def _fetch_playlist_tracks(tidal_playlist: tidalapi.Playlist, fetch_albums: bool = False,
                           fetch_albums_tracks: bool = False) -> List[Track]:
    """Fetch tracks from a TIDAL playlist."""
    total = tidal_playlist.num_tracks
    tracks = []
    for offset in range(0, total, 100):
        for track in tidal_playlist.tracks(offset=offset, limit=100):
            album = track.session.album(track.album.id) if fetch_albums else None
            if album:
                track.album = album
            tracks.append(_parse_track(track, fetch_album_tracks=fetch_albums_tracks))

    return tracks


def create_temp_session_tidal(config: tidalapi.Config = tidalapi.Config()) -> tidalapi.Session:
    """Get the URL for logging in with TIDAL using PKCE flow."""
    return tidalapi.Session(config=config)


class TidalManager(Manager):
    PLATFORM = Platform.TIDAL

    def __init__(self, username: str, db_session: Session):
        self.username = username
        self.db_session = db_session

        # Initialize TIDAL session
        self.client = tidalapi.Session()
        account = db_session.exec(
            select(TidalAccount).where(TidalAccount.username == self.username)
        ).first()
        if not account:
            raise ValueError(f"No TIDAL account found for username {username}")

        self.client.load_oauth_session(
            access_token=account.access_token,
            refresh_token=account.refresh_token,
            token_type="Bearer",
            is_pkce=True
        )
        self.client.audio_quality = _get_tidal_quality(TrackQuality.HIGH)

    def is_multi_user(self) -> bool:
        return False

    @rate_limit
    def get_track(self, track_id: str) -> Optional[TidalTrack]:
        try:
            tidal_track = self.client.track(track_id)
            if tidal_track:
                return _parse_track(tidal_track)

            return None
        except ObjectNotFound as e:
            log.exception(f"Failed to fetch TIDAL track with ID {track_id}: {e}")
            return None
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"An error occurred while fetching TIDAL track with ID {track_id}: {e}")
            return None

    @rate_limit
    def get_album(self, album_id: str) -> Optional[TidalAlbum]:
        try:
            tidal_album = self.client.album(album_id)
            if tidal_album:
                return _parse_album(tidal_album, fetch_album_tracks=True)

            return None
        except ObjectNotFound as e:
            log.exception(f"Failed to fetch TIDAL album with ID {album_id}: {e}")
            return None
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"An error occurred while fetching TIDAL album with ID {album_id}: {e}")
            return None

    @rate_limit
    def get_artist(self, artist_id: str) -> Optional[TidalArtist]:
        try:
            tidal_artist = self.client.artist(artist_id)
            if tidal_artist:
                return _parse_artist(tidal_artist)

            return None
        except ObjectNotFound as e:
            log.exception(f"Failed to fetch TIDAL artist with ID {artist_id}: {e}")
            return None
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"An error occurred while fetching TIDAL artist with ID {artist_id}: {e}")
            return None

    @rate_limit(returns=[])
    def get_artist_tracks(self, artist_id: str) -> list[TidalTrack]:
        return []  # TODO: implement fetching artist tracks

    @rate_limit
    def get_playlist(self, playlist_id: str, fetch_tracks: bool = True, fetch_albums: bool = False,
                     fetch_albums_tracks: bool = False) -> Optional[
        TidalPlaylist]:
        if playlist_id == "favorite_tracks":
            return self.get_favorite_tracks()

        if "tidal.com/playlist" in playlist_id and "http" in playlist_id:
            playlist_id = playlist_id.split("/")[-1].split("?")[0]

        try:
            tidal_playlist = self.client.playlist(playlist_id)
            if tidal_playlist:
                return _parse_playlist(tidal_playlist, fetch_tracks=fetch_tracks, fetch_albums=fetch_albums,
                                       fetch_albums_tracks=fetch_albums_tracks)
            return None
        except ObjectNotFound as e:
            log.exception(f"Failed to fetch TIDAL playlist with ID {playlist_id}: {e}")
            return None
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"An error occurred while fetching TIDAL playlist with ID {playlist_id}: {e}")
            return None

    @rate_limit(returns=[])
    def get_user_playlists(self, user_id: str = None) -> list[TidalPlaylist]:
        """Retrieve all playlists for a user."""
        try:
            if not user_id:
                playlists = self.client.user.playlists()
            else:
                playlists = self.client.get_user(int(user_id)).playlists()

            return [_parse_playlist(playlist, False) for playlist in playlists]
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to fetch TIDAL playlists for user {user_id}: {e}")
            return []

    @rate_limit
    def get_favorite_tracks(self, user_id: str = None) -> Optional[TidalFavoriteTracksPlaylist]:
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
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception("Failed to fetch favorite tracks from TIDAL")
            return None

    @rate_limit
    def _search(self,
                query: str,
                models: Optional[List[tidalapi.Album or tidalapi.Track or tidalapi.Artist]] = None,
                limit: int = 7
                ) -> Optional[SearchResults]:
        """
        Performs a search on TIDAL with the given query and types.

        :param query: The search query string.
        :param models: A list of types to search for (default: Track, available: Track, Album, Artist).
        :param limit: Maximum number of results to return (default: 7).

        :return: Search results.
        """
        try:
            sanitized_query = query[:99]  # Ensure query length does not exceed TIDAL limits
            models = models or [media.Track]
            return self.client.search(sanitized_query, limit=limit, models=models)
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to search TIDAL with query '{query}': {e}")
            return None

    @rate_limit(returns=[])
    def search_tracks_by_query(self, query: str) -> list[TidalTrack]:
        try:
            search_results = self._search(query, models=[media.Track])
            if not search_results or not search_results.get('tracks'):
                return []

            return [_parse_track(track) for track in search_results.get('tracks', [])]
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to search TIDAL tracks with query '{query}': {e}")
            return []

    @rate_limit(returns=[])
    def search_tracks_by_isrc(self, isrc: str) -> list[TidalTrack]:
        try:
            tracks = self.client.get_tracks_by_isrc(isrc)
            return [_parse_track(track) for track in tracks] if tracks else []
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to search TIDAL tracks with ISRC '{isrc}': {e}")
            return []

    @rate_limit(returns=[])
    def search_albums_by_query(self, query: str) -> list[TidalAlbum]:
        try:
            search_results = self._search(query, models=[media.Album])
            if not search_results or not search_results.get('albums'):
                return []

            return [_parse_album(album) for album in search_results.get('albums', [])]
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to search TIDAL albums with query '{query}': {e}")
            return []

    @rate_limit(returns=[])
    def search_albums_by_upc(self, upc: str) -> list[TidalAlbum]:
        try:
            albums = self.client.get_albums_by_barcode(upc)
            return [_parse_album(album) for album in albums] if albums else []
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to search TIDAL albums with UPC '{upc}': {e}")
            return []

    @rate_limit(returns=[])
    def search_artists_by_query(self, query: str) -> list[TidalArtist]:
        try:
            search_results = self._search(query, models=[tidalapi.Artist])
            if not search_results or not search_results.get('artists'):
                return []

            return [_parse_artist(artist) for artist in search_results.get('artists', [])]
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to search TIDAL artists with query '{query}': {e}")
            return []

    def supports_lyrics(self) -> bool:
        return True

    @rate_limit
    def get_lyrics(self, track: TidalTrack) -> Optional[str]:
        try:
            request = self.client.request.request("GET", "tracks/%s/lyrics" % track.id)
            json_obj = request.json()
            lyrics = self.client.request.map_json(json_obj, parse=Lyrics().parse)
            assert not isinstance(lyrics, list)

            lyrics = cast("Lyrics", lyrics)
            return lyrics.subtitles or lyrics.text
        except TooManyRequests as e:
            raise e
        except ObjectNotFound | Exception:
            log.exception(f"Lyrics not found for track {track.name} by {track.artist.name}")
            return None

    @rate_limit
    def create_empty_playlist(self, name: str, description: str = "", cover: bytes = None, user_id: str = None) -> \
            Optional[TidalPlaylist]:
        try:
            new_playlist = self.client.user.create_playlist(title=name, description=description)
            # TODO: Handle cover
            return _parse_playlist(new_playlist, fetch_tracks=False)
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to create TIDAL playlist '{name}': {e}")
            return None

    @rate_limit(returns=False)
    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[TidalTrack], user_id: str = None) -> bool:
        try:
            tidal_playlist = self.client.playlist(playlist.id)

            for i in range(0, len(tracks), 100):
                tidal_playlist.add([track.id for track in tracks[i:i + 100]])

            return True
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to add tracks to TIDAL playlist '{playlist.id}': {e}")
            return False

    @rate_limit(returns=False)
    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        try:
            tidal_playlist = self.client.playlist(playlist_id)
            tidal_playlist.delete()
            return True
        except ObjectNotFound as e:
            log.exception(f"Playlist with ID {playlist_id} not found: {e}")
            return False
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to remove TIDAL playlist with ID {playlist_id}: {e}")
            return False

    def supports_downloading(self) -> bool:
        return True

    @rate_limit
    def _get_stream(self, track: TidalTrack, quality: TrackQuality) -> StreamManifest | None:
        try:
            params = {
                "playbackmode": "STREAM",
                "assetpresentation": "FULL",
                "audioquality": _get_tidal_quality(quality),
            }

            request = self.client.request.request("GET", "tracks/%s/playbackinfopostpaywall" % track.id, params)
        except ObjectNotFound:
            log.exception(f"No stream available for track {track.name} by {track.artist.name}")
            return None
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to get stream for track {track.name} by {track.artist.name}: {e}")
            return None
        else:
            json_obj = request.json()
            stream = self.client.request.map_json(json_obj, parse=Stream().parse)
            assert not isinstance(stream, list)
            stream = cast("Stream", stream)

        if not stream:
            log.error(f"No stream manifest available for track {track.name} by {track.artist.name}")
            return None

        # Get stream manifest
        stream_manifest = stream.get_stream_manifest()
        if not stream_manifest:
            log.error(f"No stream manifest available for track {track.name} by {track.artist.name}")
            return None

        return stream_manifest

    @rate_limit
    def download_album(self, album: TidalAlbum, destination: Path, user_id: str = None,
                       quality: TrackQuality = TrackQuality.HIGH) -> \
            Optional[str]:
        # Set quality for the download
        self.client.audio_quality = _get_tidal_quality(quality)

        if not album.tracks:
            album = self.get_album(album.id)
            if not album or not album.tracks:
                log.error(f"No tracks found for album {album.name} by {album.artist.name}")
                return None

        fail = False
        try:
            for track in album.tracks:
                track_stream = self._get_stream(track, quality)
                if not track_stream:
                    log.error(f"Skipping track {track.name} by {track.artist.name} due to missing stream.")
                    continue

                print("Downloading track:", track.name)
                audio_bytes = download_all_ordered(track_stream.urls)

                # Check audio format and convert if necessary
                if track_stream.file_extension not in [AudioExtensions.M4A, AudioExtensions.FLAC]:
                    log.error(
                        f"Unsupported file extension {track_stream.file_extension} for track {track.name} by {track.artist.name}")
                    return None

                if track_stream.file_extension == AudioExtensions.M4A:
                    audio_bytes = convert_m4a_bytes_to_flac(audio_bytes, timeout=15, re_encode_flac=False)

                # Save to file
                bytes_response = bytes(audio_bytes)
                file_path = generate_path(track, base_path=destination, extension="flac")
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "wb") as f:
                    f.write(bytes_response)

                # TODO: handle metadata

                print("Downloaded bytes:", len(audio_bytes))
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to download album {album.name} by {album.artist.name}: {e}")
            fail = True

        return str(destination)

    @rate_limit
    def download_track(self, track: TidalTrack, user_id: str = None, quality: TrackQuality = TrackQuality.HIGH) -> \
            Optional[str]:
        # NOT WORKING WELL: focus on download_album first

        # Get stream info
        stream = None
        try:
            params = {
                "playbackmode": "STREAM",
                "audioquality": _get_tidal_quality(quality),
                "assetpresentation": "FULL",
            }

            request = self.client.request.request("GET", "tracks/%s/playbackinfopostpaywall" % track.id, params)
        except ObjectNotFound:
            log.exception(f"No stream available for track {track.name} by {track.artist.name}")
            return None
        except TooManyRequests as e:
            raise e
        except Exception as e:
            log.exception(f"Failed to get stream for track {track.name} by {track.artist.name}: {e}")
            return None
        else:
            json_obj = request.json()
            stream = self.client.request.map_json(json_obj, parse=Stream().parse)
            assert not isinstance(stream, list)
            stream = cast("Stream", stream)

        if not stream:
            log.error(f"No stream manifest available for track {track.name} by {track.artist.name}")
            return None

        # Get stream manifest
        stream_manifest = stream.get_stream_manifest()
        if not stream_manifest:
            log.error(f"No stream manifest available for track {track.name} by {track.artist.name}")
            return None

        # Determine file extension
        match stream_manifest.file_extension:
            case AudioExtensions.M4A:
                file_extension = "m4a"
            case AudioExtensions.FLAC:
                file_extension = "flac"
            case AudioExtensions.MP4:
                log.error(f"TIDAL MP4 streams are not supported for track {track.name} by {track.artist.name}")
                return None
            case _:
                log.error(f"Unknown TIDAL stream format for track {track.name} by {track.artist.name}")
                return None

        # Get download URLs
        download_urls = stream_manifest.urls

        # Download the track data
        audio_bytes = bytearray()
        for url in download_urls:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            audio_bytes.extend(response.content)

        # Convert M4A to FLAC if necessary
        if file_extension == "m4a":
            audio_bytes = convert_m4a_bytes_to_flac(audio_bytes, timeout=15, re_encode_flac=False)

        # Save to temporary file
        bytes_response = bytes(audio_bytes)
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_file:
            temp_file.write(bytes_response)
            temp_file_path = temp_file.name

            track_metadata = process_metadata(track, Path(temp_file_path))

            # acoustid = get_acoustid_fingerprint(Path(temp_file_path))
            # log.debug(f"AcoustID fingerprint for track {track.name} by {track.artist.name}: {acoustid}")
            #
            # musicbrainzid = query_musicbrainz_by_acoustid(acoustid)

        # return bytes(bytes_response), file_extension

        return None

# OLD CODE TO MIGRATE

# def download_track(self,
#                    track: Track,
#                    quality: TrackQuality = TrackQuality.HI_RES_LOSSLESS,
#                    output_type: str = "flac",
#                    destination: str = "~/Music/Syncphony",
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
#                       destination: str = "~/Music/Syncphony",
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
