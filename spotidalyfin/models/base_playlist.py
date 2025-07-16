from dataclasses import dataclass, field
from typing import List, Optional

from .enums import ArtistRole


@dataclass
class Playlist:
    name: str
    id: str
    tracks: List['Track'] = field(default_factory=list)
    image: str = ""

class SpotifyPlaylist(Playlist):
    """A class representing a Spotify playlist."""
    pass


@dataclass
class FavoriteTracksPlaylist(Playlist):
    id = "favorite_tracks"
