from enum import Enum


class Platform(Enum):
    TIDAL = "TIDAL"
    SPOTIFY = "SPOTIFY"
    JELLYFIN = "JELLYFIN"
    SUBSONIC = "SUBSONIC"


class TrackQuality(Enum):
    DOLBY_ATMOS = 0
    LOW = 1
    LOSSLESS = 2
    HI_RES_LOSSLESS = 3


class ArtistRole(Enum):
    MAIN = "MAIN"
    FEATURED = "FEATURED"
    CONTRIBUTOR = "CONTRIBUTOR"
    ARTIST = "ARTIST"
