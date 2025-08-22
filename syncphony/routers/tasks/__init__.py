from fastapi import APIRouter, Depends
from sqlmodel import select, Session, col

from syncphony.db.db import get_session
from syncphony.db.models import Tasks

router = APIRouter()


@router.get("/list")
async def get_tasks_list(db: Session = Depends(get_session)):
    """
    Get the current tasks list.
    """
    req = select(Tasks).order_by(col(Tasks.created_at).desc())
    tasks = db.exec(req).all()

    return {
        "tasks": [
            {
                "id": task.id,
                "status": task.status,
                "details": task.details,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            } for task in tasks
        ]
    }

@router.get("/{task_id}")
async def get_task_details(task_id: str, db: Session = Depends(get_session)):
    """
    Get details of a specific task by ID.
    """
    task = db.get(Tasks, task_id)
    if not task:
        return {"error": "Task not found"}

    return {
        "id": task.id,
        "status": task.status,
        "details": task.details,
        "logs": task.logs,
        "warnings": task.warnings,
        "errors": task.errors,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }