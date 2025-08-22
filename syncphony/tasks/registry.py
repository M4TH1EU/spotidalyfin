from typing import Callable, Dict

from syncphony.tasks.sync_playlist import task_sync
from syncphony.types.enums import TaskType

TaskHandler = Callable[..., bool]

TASK_REGISTRY: Dict[TaskType, TaskHandler] = {
    TaskType.SYNC: task_sync,
}
