from typing import Optional

from sqlmodel import Session

from syncphony.managers.spotify_manager import SpotifyManager
from syncphony.managers.tidal_manager import TidalManager
from syncphony.types.enums import Platform
from syncphony.types.manager import Manager


def get_manager_for_platform(db_session: Session, from_platform: Platform, from_account: str) -> Optional[Manager]:
    """
    Get the appropriate manager for the given platform and account.
    """
    if from_account is None:
        return None

    if from_platform == Platform.SPOTIFY:
        return SpotifyManager(
            username=from_account,
            db_session=db_session,
        )
    elif from_platform == Platform.TIDAL:
        return TidalManager(
            username=from_account,
            db_session=db_session,
        )
    elif from_platform == Platform.JELLYFIN:
        pass
    elif from_platform == Platform.SUBSONIC:
        pass
