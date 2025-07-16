from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import List, Optional

from spotidalyfin.models import Track, Album, Artist
from spotidalyfin.models.base_playlist import Playlist, FavoriteTracksPlaylist


@dataclass
class Manager(ABC):

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
    def get_playlist(self, playlist_id: str, fetch_tracks: bool = False, fetch_albums: bool = False) -> Optional[Playlist]:
        """Retrieve a playlist by its ID."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def get_user_playlists(self, user_id: str = None) -> list[Playlist]:
        """Retrieve all playlists for a user."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def get_favorite_tracks(self) -> Optional[FavoriteTracksPlaylist]:
        """Retrieve the favorite tracks playlist."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    def search_tracks(self, query: str = None, artist_name: str = None, isrc: str = None) -> list[Track]:
        """Search for tracks based on a query, artist name, or ISRC code."""
        results = []

        if isrc:
            results = self.search_tracks_by_isrc(isrc)

        if not results:
            if query and artist_name:
                results = self.search_tracks_by_query(f"{query} {artist_name}")
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

    @abstractmethod
    def search_albums(self, query: str) -> list[Album]:
        """Search for albums based on a query."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def search_artists(self, query: str) -> list[Artist]:
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

    @abstractmethod
    def create_playlist(self, name: str, tracks: List[Track], description: str = "", cover_url: str = "") -> Playlist:
        """Create a new playlist."""
        raise NotImplementedError("This method should be implemented by subclasses.")
