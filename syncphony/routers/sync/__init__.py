from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Query
from sqlmodel import Session, select, col

from syncphony.db.db import get_session
from syncphony.db.models import Tasks
from syncphony.types.enums import Platform, TaskStatus, TaskType
from syncphony.utils.managers import get_manager_for_platform

router = APIRouter()


@router.post("/start")
async def start_sync(
        ids: Annotated[list[str], Query(title="List of IDs to sync",
                                        description="IDs of the items to sync from the source platform")],
        from_platform: Platform,
        to_platform: Platform,
        from_account: str,
        to_account: str,
        from_user: str = None,
        to_user: str = None,
        db: Session = Depends(get_session)
) -> str:
    """
    Start a sync task between two platforms.
    """
    # Validate platforms
    if from_platform not in Platform:
        raise HTTPException(status_code=400, detail="Invalid source platform")
    if to_platform not in Platform:
        raise HTTPException(status_code=400, detail="Invalid destination platform")
    if from_platform == to_platform:
        raise HTTPException(status_code=400, detail="Source and destination platforms cannot be the same")

    # Validate accounts
    from_manager = get_manager_for_platform(db, from_platform, from_account)
    if not from_manager:
        raise HTTPException(status_code=404, detail="Source account not found or not supported")

    to_manager = get_manager_for_platform(db, to_platform, to_account)
    if not to_manager:
        raise HTTPException(status_code=404, detail="Destination account not found or not supported")

    # Start the sync task
    task = Tasks(
        id=str(uuid4()),
        task_type=TaskType.SYNC,
        status=TaskStatus.PENDING,
        details={
            "from_platform": from_platform.value,
            "to_platform": to_platform.value,
            "from_account": from_account,
            "to_account": to_account,
            "from_user": from_user,
            "to_user": to_user,
            "ids": ids
        }
    )
    db.add(task)
    db.commit()

    return task.id
