import requests
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlmodel import Session

from syncphony.db.db import get_session
from syncphony.db.models import JellyfinAccount

router = APIRouter()


@router.post("/jellyfin/add")
def add_jellyfin_account(
        server_url: str = Query(...),
        api_key: str = Query(..., min_length=32, max_length=32),
        db: Session = Depends(get_session)
):
    if not server_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid server URL format")
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    jellyfin_account = JellyfinAccount(
        url=server_url,
        api=api_key
    )

    # Test Jellyfin API on /Users
    try:
        # Assuming you have a function to test the Jellyfin API
        # This should raise an exception if the connection fails
        resp = requests.get(f"{server_url}/Users", headers={"X-Emby-Token": api_key}, timeout=5)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to connect to Jellyfin server, check URL and API key")
        json = resp.json()
        if not json or len(json) == 0:
            raise HTTPException(status_code=400,
                                detail="No users found on the Jellyfin server, check API key permissions")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Jellyfin server: {str(e)}")

    db.add(jellyfin_account)
    db.commit()
    db.refresh(jellyfin_account)

    return {"message": "Jellyfin account linked successfully", "account": jellyfin_account}
