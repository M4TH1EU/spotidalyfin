import io
import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from queue import Queue, Empty

from sqlmodel import select, Session

from syncphony.constants import TASKS_MAX_CONCURRENT, TASKS_POLL_INTERVAL
from syncphony.db.db import engine
from syncphony.db.models import Tasks
from syncphony.tasks.registry import TASK_REGISTRY
from syncphony.types.enums import TaskStatus

logger = logging.getLogger("task_runner")


class TaskLogHandler(logging.Handler):
    """
    Captures logs into a queue for async flushing into the DB.
    """

    def __init__(self, task_id: str, queue: Queue):
        super().__init__()
        self.task_id = task_id
        self.queue = queue

    def emit(self, record):
        msg = self.format(record)
        entry = {
            "task_id": self.task_id,
            "level": record.levelno,
            "message": msg,
            "timestamp": record.created,
        }
        self.queue.put(entry)


class TaskRunner:
    def __init__(self, max_workers: int = TASKS_MAX_CONCURRENT, poll_interval: int = TASKS_POLL_INTERVAL):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self._task_loop, daemon=True)

        # log queue and flusher thread
        self.log_queue: Queue = Queue()
        self.log_thread = threading.Thread(target=self._flush_logs_loop, daemon=True)

    def start(self):
        self._reset_stale_tasks()
        logger.info("Starting TaskRunner...")
        self.thread.start()
        self.log_thread.start()

    def stop(self):
        logger.info("Stopping TaskRunner...")
        self._stop_event.set()
        self.executor.shutdown(wait=True)
        self.log_thread.join(timeout=2)

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

    def _run_task(self, task_id: str):
        with Session(engine) as db:
            task = db.get(Tasks, task_id)
            if not task:
                logger.error("Task %s not found in DB", task_id)
                return

            handler = TASK_REGISTRY.get(task.type)

            # per-task logger
            task_logger = logging.getLogger(f"task_runner.{task.id}")
            task_logger.setLevel(logging.DEBUG)
            task_logger.propagate = False

            log_handler = TaskLogHandler(task.id, self.log_queue)
            log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            task_logger.addHandler(log_handler)

            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()

            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                try:
                    if not handler:
                        raise RuntimeError(f"No handler registered for task type {task.type}")

                    task_logger.info("Starting task %s of type %s", task.id, task.type)
                    success = handler(db, task)

                    if success:
                        task.status = TaskStatus.COMPLETED
                    else:
                        task.status = TaskStatus.FAILED
                        task.errors += "Task returned unsuccessful result.\n"

                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.errors += f"Exception: {str(e)}\n{traceback.format_exc()}"
                    task_logger.exception("Task %s failed with exception", task.id)
                finally:
                    # stdout/stderr
                    out, err = stdout_buf.getvalue(), stderr_buf.getvalue()
                    if out:
                        self.log_queue.put({"task_id": task.id, "level": logging.INFO, "message": out})
                    if err:
                        self.log_queue.put({"task_id": task.id, "level": logging.ERROR, "message": err})

                    db.add(task)
                    db.commit()

            task_logger.removeHandler(log_handler)

    def _flush_logs_loop(self):
        """
        Continuously flush logs from the queue into the DB.
        Runs as a background thread.
        """
        while not self._stop_event.is_set():
            try:
                entry = self.log_queue.get(timeout=1)
            except Empty:
                continue

            with Session(engine) as db:
                task = db.get(Tasks, entry["task_id"])
                if not task:
                    continue
                msg = f"{entry['timestamp']:.0f}: {entry['message']}\n"
                if entry["level"] >= logging.ERROR:
                    task.errors += msg
                elif entry["level"] >= logging.WARNING:
                    task.warnings += msg
                else:
                    task.logs += msg
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
                        self.executor.submit(self._run_task, task.id)

            except Exception as e:
                logger.exception(f"Error in task runner loop: {e}")

            time.sleep(self.poll_interval)
