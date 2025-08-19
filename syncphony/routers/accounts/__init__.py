from enum import Enum

from fastapi import APIRouter, Depends
from sqlmodel import select, Session

from syncphony.db.db import get_session
from syncphony.db.models import SpotifyAccount, TidalAccount
from syncphony.types.enums import Platform
from syncphony.routers.accounts import spotify, tidal, jellyfin, subsonic

router = APIRouter()
router.include_router(spotify.router)
router.include_router(tidal.router)
router.include_router(jellyfin.router)
router.include_router(subsonic.router)


@router.get("/list")
def get_accounts(db: Session = Depends(get_session)):
    return {
        Platform.SPOTIFY: {
            "users": [account.username for account in db.exec(select(SpotifyAccount)).all()]
        },
        Platform.TIDAL: {
            "users": [account.username for account in db.exec(select(TidalAccount)).all()]
        },
        Platform.JELLYFIN: {
            "servers": [account.url for account in db.exec(select(jellyfin.JellyfinAccount)).all()]
        },
        Platform.SUBSONIC: {
            "servers": [account.url for account in db.exec(select(subsonic.SubsonicAccount)).all()]
        },
    }


@router.delete("/remove/{account_type}/{id}")
def remove_account(account_type: Platform, id: str):
    if account_type not in Platform.__dict__.values():
        return {"error": "Invalid account type"}

    # Here you would call the appropriate function to remove the account
    # For example:
    # if account_type == "spotify":
    #     remove_spotify_profile(username)

    return {"message": f"{account_type.value.capitalize()} account '{id}' removed successfully."}
