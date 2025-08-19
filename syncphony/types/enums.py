from enum import Enum


class Platform(str, Enum):
    TIDAL = "tidal"
    SPOTIFY = "spotify"
    JELLYFIN = "jellyfin"
    SUBSONIC = "subsonic"


class TrackQuality(int, Enum):
    UNKNOWN = 0
    LOW = 1  # < 320K
    MEDIUM = 2  # >= 320K
    HIGH = 3  # Lossless (CD/FLAC)
    EXTREME = 4  # Hi-Res Lossless (24-bit/192kHz)
    DOLBY_ATMOS = 5  # Dolby Atmos


class ArtistRole(str, Enum):
    MAIN = "MAIN"
    FEATURED = "FEATURED"
    CONTRIBUTOR = "CONTRIBUTOR"
    ARTIST = "ARTIST"

class TaskType(str, Enum):
    SYNC = "sync"
    DOWNLOAD = "download"

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"