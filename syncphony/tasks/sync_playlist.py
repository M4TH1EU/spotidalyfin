from sqlmodel import Session

from syncphony.db.models import Tasks
from syncphony.tasks.logging import get_task_logger
from syncphony.types import Track
from syncphony.types.enums import TaskStatus
from syncphony.types.utils import get_track_on_another_platform
from syncphony.utils.managers import get_manager_for_platform


def task_sync(db: Session, task: Tasks) -> bool:
    """
    Task to perform synchronization between platforms.
    This function is called by the task runner.
    """
    logger = get_task_logger(task)

    task.status = TaskStatus.IN_PROGRESS
    db.add(task)
    db.commit()

    details = task.details
    from_platform = details.get("from_platform")
    from_account = details.get("from_account")
    from_user = details.get("from_user")
    to_platform = details.get("to_platform")
    to_account = details.get("to_account")
    to_user = details.get("to_user")

    if not from_platform or not from_account or not to_platform or not to_account:
        task.status = TaskStatus.FAILED
        db.add(task)
        db.commit()
        logger.error("Invalid task details: missing platform or account information.")
        return False

    from_manager = get_manager_for_platform(db, from_platform, from_account, user=from_user, logger=logger)
    to_manager = get_manager_for_platform(db, to_platform, to_account, user=to_user, logger=logger)

    if not from_manager or not to_manager:
        task.status = TaskStatus.FAILED
        db.add(task)
        db.commit()
        logger.error("Invalid task details: missing manager for platform or account.")
        return False

    overall_success = True

    try:
        for playlist_id in details.get("ids", []):
            playlist = from_manager.get_playlist(playlist_id)
            if not playlist or not playlist.tracks:
                continue

            to_tracks: list[Track] = []
            for track in playlist.tracks:
                to_track = get_track_on_another_platform(track, to_manager)
                if to_track:
                    logger.info("Found track %s on %s", track.name, to_platform)
                    to_tracks.append(to_track)
                else:
                    logger.warning("Track %s not found on %s, skipping", track.name, to_platform)

            if not to_tracks:
                continue

            to_playlist = to_manager.create_playlist(
                playlist.name, to_tracks, playlist.description, to_user
            )

            if not to_playlist:
                logger.error("Failed to create playlist %s on %s", playlist.name, to_platform)
                overall_success = False
            else:
                logger.info(
                    "Successfully created playlist %s on %s with %d tracks",
                    to_playlist.name, to_platform, len(to_tracks)
                )

        task.status = TaskStatus.COMPLETED if overall_success else TaskStatus.FAILED
        db.add(task)
        db.commit()
        return overall_success

    except Exception as e:
        task.status = TaskStatus.FAILED
        db.add(task)
        db.commit()
        logger.exception("Task failed with exception: %s", e)
        return False
