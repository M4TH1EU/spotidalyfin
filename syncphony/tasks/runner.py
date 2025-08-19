# Thread-safe executor for running tasks
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func
from sqlmodel import select, Session

from syncphony.constants import TASKS_MAX_CONCURRENT, TASKS_POLL_INTERVAL
from syncphony.db.db import get_session, engine
from syncphony.db.models import Tasks
from syncphony.tasks.sync_playlist import task_sync
from syncphony.types.enums import TaskStatus, TaskType

executor = ThreadPoolExecutor(max_workers=TASKS_MAX_CONCURRENT)
lock = threading.Lock()  # to avoid race conditions when querying/updating tasks


def run_task(task: Tasks):
    """
    Placeholder function that runs a task based on its type.
    """
    with Session(engine) as db:
        success = False

        if task.task_type == TaskType.SYNC:
            success = task_sync(db, task)

        if not success:
            task.status = TaskStatus.FAILED
            task.errors += "Task execution failed.\n"
        else:
            task.status = TaskStatus.COMPLETED
            task.logs += "Task executed successfully.\n"

        db.add(task)
        db.commit()


def task_runner_loop():
    """
    This loop polls the DB for pending tasks and submits them to the executor.
    """
    while True:
        try:
            with lock:
                with Session(engine) as db:
                    # Check currently running tasks
                    running_count = db.exec(
                        select(func.count(Tasks.id)).where(Tasks.status == TaskStatus.IN_PROGRESS)
                    ).one()

                    # Fetch pending tasks
                    pending_tasks = db.exec(
                        select(Tasks).where(Tasks.status == TaskStatus.PENDING)
                    ).all()

                    # Start tasks up to max concurrency
                    for task in pending_tasks:
                        if running_count >= TASKS_MAX_CONCURRENT:
                            break
                        # Mark task as running
                        task.status = TaskStatus.IN_PROGRESS
                        db.add(task)
                        db.commit()

                        executor.submit(run_task, task)
                        running_count += 1

        except Exception as e:
            print(f"Error in task runner loop: {e}")

        time.sleep(TASKS_POLL_INTERVAL)


def start_task_runner():
    # Mark all previous tasks as FAILED if they are still IN_PROGRESS
    with Session(engine) as db:
        running_tasks = db.exec(
            select(Tasks).where(Tasks.status == TaskStatus.IN_PROGRESS)
        ).all()
        for task in running_tasks:
            task.status = TaskStatus.FAILED
            db.add(task)
        db.commit()

    thread = threading.Thread(target=task_runner_loop, daemon=True)
    thread.start()
