from enum import Enum


class Platform(Enum):
    TIDAL = "TIDAL"
    SPOTIFY = "SPOTIFY"
    JELLYFIN = "JELLYFIN"
    SUBSONIC = "SUBSONIC"


class TrackQuality(Enum):
    UNKNOWN = 0
    LOW = 1  # < 320K
    MEDIUM = 2  # >= 320K
    HIGH = 3  # Lossless (CD/FLAC)
    EXTREME = 4  # Hi-Res Lossless (24-bit/192kHz)
    DOLBY_ATMOS = 5  # Dolby Atmos


class ArtistRole(Enum):
    MAIN = "MAIN"
    FEATURED = "FEATURED"
    CONTRIBUTOR = "CONTRIBUTOR"
    ARTIST = "ARTIST"
