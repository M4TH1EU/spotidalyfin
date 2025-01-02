import json
from typing import List, Optional

import cachebox
import tidalapi
from tidalapi import media
from tidalapi.exceptions import ObjectNotFound
from tidalapi.session import SearchResults

from spotidalyfin import cfg
from spotidalyfin.db.database import Database
from spotidalyfin.db.helpers import save_tidal_info_to_db, get_tidal_login_info, get_authenticated_tidal_profiles
from spotidalyfin.managers import types
from spotidalyfin.managers.types import Track, Album, Artist, TrackQuality
from spotidalyfin.utils.decorators import rate_limit


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
        self.client.load_oauth_session(**get_tidal_login_info(db, username), token_type="Bearer", is_pkce=True)
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
