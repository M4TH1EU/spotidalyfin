from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Query
from sqlmodel import Session

from syncphony.db.db import get_session
from syncphony.db.models import Tasks
from syncphony.types.enums import Platform, TaskStatus, TaskType, TrackQuality
from syncphony.utils.managers import get_manager_for_platform

router = APIRouter()


@router.post("/start")
async def start_download(
        ids: Annotated[list[str], Query(title="List of IDs to download",
                                        description="IDs of the playlists to download from the platform")],
        destination: str,
        from_platform: Platform,
        from_account: str,
        from_user: str | None = None,
        download_entire_album: bool = False,
        quality: TrackQuality = TrackQuality.HIGH,
        db: Session = Depends(get_session)
) -> str:
    """
    Start a download task from a selected platform.
    """
    # Validate platform
    if from_platform not in Platform:
        raise HTTPException(status_code=400, detail="Invalid platform")

    # # Validate accounts
    # dl_manager = get_manager_for_platform(db, from_platform, from_account, from_user)
    # if not dl_manager:
    #     raise HTTPException(status_code=404, detail="Account not found or not supported")

    # Start the sync task
    task = Tasks(
        id=str(uuid4()),
        type=TaskType.DOWNLOAD,
        status=TaskStatus.PENDING,
        details={
            "from_platform": from_platform.value,
            "from_account": from_account,
            "from_user": from_user,
            "ids": ids,
            "download_entire_album": download_entire_album,
            "quality": quality.value,
            "destination": destination
        }
    )
    db.add(task)
    db.commit()

    return task.id
