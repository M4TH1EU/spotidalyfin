import logging
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import List, Optional, Tuple

from spotidalyfin.models import Track, Album, Artist
from spotidalyfin.models.compare import normalize_track_name, compare_strings, normalize_artist_name
from spotidalyfin.models.enums import Platform
from spotidalyfin.models.playlist import Playlist, FavoriteTracksPlaylist


@dataclass
class Manager(ABC):
    PLATFORM: Platform

    @abstractmethod
    def is_multi_user(self) -> bool:
        """Check if the manager supports multiple users."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    def get_users(self) -> List[Tuple[str, str]]:
        """Retrieve a list of users with their IDs and names."""
        if self.is_multi_user():
            raise NotImplementedError("This method should be implemented by subclasses.")
        return []

    @abstractmethod
    def get_track(self, track_id: str) -> Optional[Track]:
        """Retrieve a track by its ID."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def get_album(self, album_id: str) -> Optional[Album]:
        """Retrieve an album by its ID."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def get_artist(self, artist_id: str) -> Optional[Artist]:
        """Retrieve an artist by its ID."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def get_artist_tracks(self, artist_id: str) -> List[Track]:
        """Retrieve all tracks by an artist."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def get_playlist(self, playlist_id: str, fetch_tracks: bool = True, fetch_albums: bool = False) -> Optional[
        Playlist]:
        """Retrieve a playlist by its ID."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def get_user_playlists(self, user_id: str = None) -> list[Playlist]:
        """Retrieve all playlists for a user. Playlists tracks are not expected to be fetched"""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def get_favorite_tracks(self, user_id: str = None) -> Optional[FavoriteTracksPlaylist]:
        """Retrieve the favorite tracks playlist."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    def search_tracks(self, query: str = None, artist_name: str = None, isrc: str = None) -> list[Track]:
        """Search for tracks based on a query, artist name, or ISRC code."""
        results = []

        if isrc:
            results = self.search_tracks_by_isrc(isrc)

        if not results:
            if query and artist_name:
                # artists = self.search_artists_by_query(artist_name)
                results = self.search_tracks_by_query(f"{query} {artist_name}")
                if not results:
                    results = self.search_tracks_by_query(query)

                    if not results:
                        results = self.search_tracks_by_query(normalize_track_name(query))

                        if not results:
                            artists = self.search_artists_by_query(artist_name)
                            if not artists:
                                artists = self.search_artists_by_query(normalize_artist_name(artist_name))

                            if not artists:
                                return []

                            best_artist_match = max(artists, key = lambda a: compare_strings(a.name, artist_name), default=None)
                            results = self.get_artist_tracks(best_artist_match.id)
            elif query:
                results = self.search_tracks_by_query(query)
            elif artist_name:
                results = self.search_tracks_by_query(artist_name)

        return results

    @abstractmethod
    def search_tracks_by_query(self, query: str) -> list[Track]:
        """Search for tracks based on a query."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def search_tracks_by_isrc(self, isrc: str) -> list[Track]:
        """Search for tracks by ISRC code."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    def search_albums(self, query: str = None, upc: str = None) -> list[Album]:
        """Search for albums based on a query or UPC code."""
        results = []

        if upc:
            results = self.search_albums_by_upc(upc)

        if not results:
            if query:
                results = self.search_albums_by_query(query)

        return results

    @abstractmethod
    def search_albums_by_query(self, query: str) -> list[Album]:
        """Search for albums based on a query."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def search_albums_by_upc(self, upc: str) -> list[Album]:
        """Search for albums based on a UPC (barcode)."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def search_artists_by_query(self, query: str) -> list[Artist]:
        """Search for artists based on a query."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def supports_lyrics(self) -> bool:
        """Check if the manager supports lyrics retrieval."""
        return False

    @abstractmethod
    def get_lyrics(self, track: Track) -> str:
        """Retrieve lyrics for a given track."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    def create_playlist(self, name: str, tracks: List[Track], description: str = "", cover: bytes = None,
                        user_id: str = None) -> Optional[
        Playlist]:
        """Create a new playlist."""

        if self.is_multi_user() and not user_id:
            logging.error("User ID is required to create playlist for multi-user platforms.")
            return None

        # Make sure to remove any existing playlist with the same name
        self.remove_playlist_by_name(name, user_id)

        # Create an empty playlist first
        new_playlist = self.create_empty_playlist(name, description, cover, user_id)
        if not new_playlist:
            logging.error(f"Failed to create empty playlist: {name}")
            return None

        # If the playlist is created successfully, add the tracks to it
        if not self.add_tracks_to_playlist(new_playlist, tracks):
            logging.error(f"Failed to add tracks to playlist: {name}")
            return None

        return new_playlist

    @abstractmethod
    def create_empty_playlist(self, name: str, description: str = "", cover: bytes = None, user_id: str = None) -> \
            Optional[Playlist]:
        """Create a new empty playlist."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    def add_tracks_to_playlist_with_id(self, playlist_id: str, tracks: List[Track]) -> bool:
        """Add tracks to an existing playlist."""
        return self.add_tracks_to_playlist(self.get_playlist(playlist_id, fetch_tracks=False), tracks)

    @abstractmethod
    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[Track]) -> bool:
        raise NotImplementedError("This method should be implemented by subclasses.")

    def remove_playlist_by_name(self, name: str, user_id: str = None) -> bool:
        """Remove a playlist by its name."""

        playlists = self.get_user_playlists(user_id=user_id)
        for playlist in playlists:
            if playlist.name == name:
                return self.remove_playlist_by_id(playlist.id)
        return False

    @abstractmethod
    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        """Remove a playlist by its ID."""
        raise NotImplementedError("This method should be implemented by subclasses.")
