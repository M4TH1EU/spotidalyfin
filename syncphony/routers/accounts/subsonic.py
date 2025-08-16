from fastapi import APIRouter, HTTPException, Query, Depends
from sqlmodel import Session

from syncphony.db.db import get_session
from syncphony.db.models import SubsonicAccount

router = APIRouter()


@router.post("/subsonic/add")
def add_jellyfin_account(
        server_url: str = Query(...),
        username: str = Query(...),
        password: str = Query(...),
        db: Session = Depends(get_session)
):
    if not server_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid server URL format")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password cannot be empty")

    subsonic_account = SubsonicAccount(
        url=server_url,
        username=username,
        password=password
    )

    # TODO: implement test of Subsonic connection

    db.add(subsonic_account)
    db.commit()
    db.refresh(subsonic_account)

    return {"message": "Subsonic account linked successfully", "account": subsonic_account}
