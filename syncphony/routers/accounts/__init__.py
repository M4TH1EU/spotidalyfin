from enum import Enum

from fastapi import APIRouter

from syncphony.routers.accounts import spotify, tidal


class AccountType(str, Enum):
    SPOTIFY = "spotify"
    TIDAL = "tidal"
    JELLYFIN = "jellyfin"
    SUBSONIC = "subsonic"


router = APIRouter()
router.include_router(spotify.router)
router.include_router(tidal.router)


@router.get("/list")
def get_accounts():
    return {
        "spotify": [],
        "tidal": [],
        "jellyfin": [],
        "subsonic": [],
    }


@router.delete("/remove/{account_type}/{id}")
def remove_account(account_type: AccountType, id: str):
    if account_type not in AccountType.__dict__.values():
        return {"error": "Invalid account type"}

    # Here you would call the appropriate function to remove the account
    # For example:
    # if account_type == "spotify":
    #     remove_spotify_profile(username)

    return {"message": f"{account_type.capitalize()} account '{id}' removed successfully."}
