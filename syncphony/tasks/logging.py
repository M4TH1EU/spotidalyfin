import logging

from syncphony.db.models import Tasks


def get_task_logger(task: Tasks) -> logging.Logger:
    """
    Returns a logger instance specific to a given task.
    Logs will be captured by the TaskRunner's TaskLogHandler.
    """
    return logging.getLogger(f"task_runner.{task.id}")