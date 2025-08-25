import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from sqlmodel import select, Session

from syncphony.constants import TASKS_MAX_CONCURRENT, TASKS_POLL_INTERVAL
from syncphony.db.db import engine
from syncphony.db.models import Tasks
from syncphony.tasks.registry import TASK_REGISTRY
from syncphony.types.enums import TaskStatus

logger = logging.getLogger("task_runner")


class TaskRunner:
    def __init__(self, max_workers: int = TASKS_MAX_CONCURRENT, poll_interval: int = TASKS_POLL_INTERVAL):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self._task_loop, daemon=True)

    def start(self):
        self._reset_stale_tasks()
        logger.info("Starting TaskRunner...")
        self.thread.start()

    def stop(self):
        logger.info("Stopping TaskRunner...")
        self._stop_event.set()
        self.executor.shutdown(wait=True)

    def _reset_stale_tasks(self):
        with Session(engine) as db:
            running_tasks = db.exec(
                select(Tasks).where(Tasks.status == TaskStatus.IN_PROGRESS)
            ).all()
            for task in running_tasks:
                task.status = TaskStatus.FAILED
                task.errors += "Task was interrupted by system restart.\n"
                db.add(task)
            db.commit()

    def _run_task(self, task: Tasks):
        handler = TASK_REGISTRY.get(task.type)
        with Session(engine) as db:
            if not handler:
                task.status = TaskStatus.FAILED
                task.errors += f"No handler registered for task type {task.type}\n"
                db.add(task)
                db.commit()
                return

            try:
                success = handler(db, task)
                if success:
                    task.status = TaskStatus.COMPLETED
                else:
                    task.status = TaskStatus.FAILED
                    task.errors += "Task returned unsuccessful result.\n"
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.errors += f"Exception: {str(e)}\n"
                logger.exception(f"Task {task.id} failed with exception")
            finally:
                db.add(task)
                db.commit()

    def _task_loop(self):
        while not self._stop_event.is_set():
            try:
                with Session(engine) as db:
                    # Fetch pending tasks
                    pending_tasks = db.exec(
                        select(Tasks)
                        .where(Tasks.status == TaskStatus.PENDING)
                        .limit(TASKS_MAX_CONCURRENT)
                    ).all()

                    for task in pending_tasks:
                        task.status = TaskStatus.IN_PROGRESS
                        db.add(task)
                        db.commit()
                        self.executor.submit(self._run_task, task)

            except Exception as e:
                logger.exception(f"Error in task runner loop: {e}")

            time.sleep(self.poll_interval)
