from pathlib import Path

from sqlmodel import Session

from syncphony.db.models import Tasks
from syncphony.types.enums import TaskStatus
from syncphony.utils.managers import get_manager_for_platform


def task_download(db: Session, task: Tasks) -> bool:
    """
    Task to perform download of playlist(s)
    This function is called by the task runner.
    """
    task.status = TaskStatus.IN_PROGRESS
    db.add(task)
    db.commit()

    details = task.details
    from_platform = details.get("from_platform")
    from_account = details.get("from_account")
    from_user = details.get("from_user")

    download_entire_album = details.get("download_entire_album", False)
    quality = details.get("quality")
    destination = details.get("destination")

    if not from_platform or not from_account or not quality:
        task.status = TaskStatus.FAILED
        db.add(task)
        db.commit()
        raise ValueError("Invalid task details: missing platform, account or quality information.")

    dl_manager = get_manager_for_platform(db, from_platform, from_account)

    if not dl_manager or not destination:
        task.status = TaskStatus.FAILED
        task.errors += f"Invalid task details: missing destination, platform or account information.\n"
        db.add(task)
        db.commit()
        return False

    destination = Path(destination)
    if not destination.exists():
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.errors += f"Failed to create destination directory: {str(e)}\n"
            db.add(task)
            db.commit()
            return False


    try:
        for playlist_id in details.get("ids", []):
            playlist = dl_manager.get_playlist(playlist_id, fetch_albums=download_entire_album, fetch_albums_tracks=download_entire_album)
            if not playlist:
                continue

            total_tracks = len(playlist.tracks)
            if total_tracks == 0:
                continue

            if download_entire_album:
                all_albums = []
                for track in playlist.tracks:
                    if track.album and track.album not in all_albums:
                        all_albums.append(track.album)

                for album in all_albums:
                    download = dl_manager.download_album(album, destination, from_user, quality)
                    if download:
                        task.logs += f"Downloaded album {album.name} by {album.artist}.\n"
                    else:
                        task.logs += f"Failed to download album {album.name} by {album.artist}.\n"
            else:
                for track in playlist.tracks:
                    download = dl_manager.download_track(track, from_user, quality)
                    if download:
                        task.logs += f"Downloaded track {track.name} by {track.artist}.\n"
                    else:
                        task.logs += f"Failed to download track {track.name} by {track.artist}.\n"

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
