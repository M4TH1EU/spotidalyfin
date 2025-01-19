class DownloadPlaylistException(Exception):
    """Base class for exceptions in this module."""
    pass


class DownloadTrackException(Exception):
    """Base class for exceptions in this module."""
    pass


class TrackNotFoundException(Exception):
    """Exception raised when a track is not found."""
    pass


class ArtistNotFoundException(Exception):
    """Exception raised when an artist is not found."""
    pass


class PlaylistNotFoundException(Exception):
    """Exception raised when a playlist is not found."""
    pass


class PlaylistItemsException(Exception):
    """Base class for exceptions in this module."""
    pass


class UserPlaylistsException(Exception):
    """Base class for exceptions in this module."""
    pass


class AlbumNotFoundException(Exception):
    """Exception raised when an album is not found."""
    pass


class LyricsNotFoundException(Exception):
    """Exception raised when lyrics are not found."""
    pass


class PlatformException(Exception):
    """Base class for exceptions in this module."""
    pass


class SearchException(Exception):
    """Exception raised when a search fails."""
    pass
