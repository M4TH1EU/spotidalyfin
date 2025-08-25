from sqlmodel import Session

from syncphony.db.models import Tasks
from syncphony.types import Track
from syncphony.types.enums import TaskStatus
from syncphony.types.utils import get_track_on_another_platform
from syncphony.utils.managers import get_manager_for_platform


def task_sync(db: Session, task: Tasks) -> bool:
    """
    Task to perform synchronization between platforms.
    This function is called by the task runner.
    """
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
        raise ValueError("Invalid task details: missing platform or account information.")

    from_manager = get_manager_for_platform(db, from_platform, from_account)
    to_manager = get_manager_for_platform(db, to_platform, to_account)

    if not from_manager or not to_manager:
        task.status = TaskStatus.FAILED
        task.errors += f"Invalid task details: missing platform or account information.\n"
        db.add(task)
        db.commit()
        return False

    try:
        for playlist_id in details.get("ids", []):
            playlist = from_manager.get_playlist(playlist_id)
            if not playlist:
                continue

            total_tracks = len(playlist.tracks)
            if total_tracks == 0:
                continue

            to_tracks: list[Track] = []
            for track in playlist.tracks:
                to_track = get_track_on_another_platform(track, to_manager)
                if to_track:
                    task.logs += f"Found track {track.name} on {to_platform}.\n"
                    to_tracks.append(to_track)
                else:
                    task.warnings += f"Track {track.name} not found on {to_platform}, skipping.\n"

            if not to_tracks:
                continue

            to_playlist = to_manager.create_playlist(playlist.name, to_tracks, playlist.description, to_user)

            if not to_playlist:
                task.status = TaskStatus.FAILED
                task.errors += f"Failed to create playlist {playlist.name} on {to_platform}.\n"
                db.add(task)
                db.commit()
            else:
                task.logs += f"Successfully created playlist {to_playlist.name} on {to_platform} with {len(to_tracks)} tracks.\n"
                task.status = TaskStatus.COMPLETED
                db.add(task)
                db.commit()
                return True
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.errors += str(e)
        db.add(task)
        db.commit()
        return False

    return False
