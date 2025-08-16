import spotipy
import tidalapi
from fastapi import APIRouter, HTTPException, Query, Depends
from spotipy import MemoryCacheHandler
from spotipy.oauth2 import SpotifyOAuth
from sqlmodel import Session, select

from syncphony.db.db import get_session
from syncphony.db.models import SpotifyAccount, TidalAccount
from syncphony.storage.oauth_spotify import store_temp_oauth, get_temp_oauth, remove_temp_oauth
from syncphony.storage.oauth_tidal import store_temp_session, get_temp_session, remove_temp_session

router = APIRouter()


@router.post("/tidal/start")
def start_tidal_auth():
    # Create temporary OAuth object
    session = tidalapi.Session(config=tidalapi.Config())

    session_id = store_temp_session(session)
    auth_url = session.pkce_login_url()

    return {"auth_url": auth_url, "session_id": session_id}


@router.post("/tidal/finish")
def finish_spotify_auth(
        session_id: str = Query(...),
        redirect_uri: str = Query(..., regex=r"^https?://"),
        db: Session = Depends(get_session)
):
    session = get_temp_session(session_id)
    if not session:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    if "code=" not in redirect_uri:
        raise HTTPException(status_code=400, detail="Invalid redirect URI, missing authorization code")

    response: dict = session.pkce_get_auth_token(redirect_uri)
    if not response or "user" not in response:
        raise HTTPException(status_code=400, detail="Failed to retrieve user information from Tidal")

    existing_accounts = select(TidalAccount).where(TidalAccount.username == response.get("user", {}).get("username"))
    existing_account = db.exec(existing_accounts).first()
    if existing_account:
        raise HTTPException(status_code=400, detail="This Tidal account is already authenticated")

    tidal_account = TidalAccount(
        username=response["user"]["username"],
        access_token=response["access_token"],
        refresh_token=response.get("refresh_token", ""),
    )

    db.add(tidal_account)
    db.commit()
    db.refresh(tidal_account)

    remove_temp_session(session_id)

    return {"message": "Spotify account linked successfully", "account": tidal_account}
