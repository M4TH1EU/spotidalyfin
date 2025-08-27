import logging
from typing import Optional

from sqlmodel import Session

from syncphony.managers.jellyfin_manager import JellyfinManager
from syncphony.managers.spotify_manager import SpotifyManager
from syncphony.managers.subsonic_manager import SubsonicManager
from syncphony.managers.tidal_manager import TidalManager
from syncphony.types.enums import Platform
from syncphony.types.manager import Manager


def get_manager_for_platform(db_session: Session, platform: Platform, account: str, user: str = None,
                             logger: logging.Logger = None) -> Optional[Manager]:
    """
    Get the appropriate manager for the given platform and account.
    """
    if account is None:
        return None

    multi_users_platforms = [Platform.SUBSONIC]
    if platform in multi_users_platforms and user is None:
        return None

    if platform == Platform.SPOTIFY:
        return SpotifyManager(
            username=account,
            db_session=db_session,
            logger=logger,
        )
    elif platform == Platform.TIDAL:
        return TidalManager(
            username=account,
            db_session=db_session,
            logger=logger,
        )
    elif platform == Platform.JELLYFIN:
        return JellyfinManager(
            url=account,
            db_session=db_session,
            logger=logger,
        )
    elif platform == Platform.SUBSONIC:
        return SubsonicManager(
            url=account,
            username=user,
            db_session=db_session,
            logger=logger,
        )
