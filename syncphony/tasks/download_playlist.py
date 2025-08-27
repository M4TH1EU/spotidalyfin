from pathlib import Path

from sqlmodel import Session

from syncphony.db.models import Tasks
from syncphony.tasks.logging import get_task_logger
from syncphony.types.enums import TaskStatus
from syncphony.utils.managers import get_manager_for_platform


def task_download(db: Session, task: Tasks) -> bool:
    """
    Task to perform download of playlist(s).
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

    download_entire_album = details.get("download_entire_album", False)
    quality = details.get("quality")
    destination = details.get("destination")

    if not from_platform or not from_account or not quality:
        task.status = TaskStatus.FAILED
        db.add(task)
        db.commit()
        logger.error("Invalid task details: missing platform, account or quality information.")
        return False

    dl_manager = get_manager_for_platform(db, from_platform, from_account, logger=logger)

    if not dl_manager or not destination:
        task.status = TaskStatus.FAILED
        db.add(task)
        db.commit()
        logger.error("Invalid task details: missing destination, platform or account information.")
        return False

    destination = Path(destination)
    if not destination.exists():
        try:
            destination.mkdir(parents=True, exist_ok=True)
            logger.info("Created destination directory: %s", destination)
        except Exception as e:
            task.status = TaskStatus.FAILED
            db.add(task)
            db.commit()
            logger.exception("Failed to create destination directory: %s", e)
            return False

    try:
        for playlist_id in details.get("ids", []):
            playlist = dl_manager.get_playlist(
                playlist_id,
                fetch_albums=download_entire_album,
                fetch_albums_tracks=download_entire_album,
            )
            if not playlist:
                logger.warning("Playlist with ID %s not found on %s", playlist_id, from_platform)
                continue

            total_tracks = len(playlist.tracks)
            if total_tracks == 0:
                logger.warning("Playlist %s contains no tracks", playlist.name)
                continue

            if download_entire_album:
                all_albums = []
                for track in playlist.tracks:
                    if track.album and track.album not in all_albums:
                        all_albums.append(track.album)

                for album in all_albums:
                    download = dl_manager.download_album(album, destination, from_user, quality)
                    if download:
                        logger.info("Downloaded album %s by %s", album.name, album.artist)
                    else:
                        logger.error("Failed to download album %s by %s", album.name, album.artist)
            else:
                for track in playlist.tracks:
                    download = dl_manager.download_track(track, from_user, quality)
                    if download:
                        logger.info("Downloaded track %s by %s", track.name, track.artist)
                    else:
                        logger.error("Failed to download track %s by %s", track.name, track.artist)

            task.status = TaskStatus.COMPLETED
            db.add(task)
            db.commit()
            logger.info(
                "Successfully processed playlist %s (%d tracks) from %s",
                playlist.name, total_tracks, from_platform
            )
            return True

    except Exception as e:
        task.status = TaskStatus.FAILED
        db.add(task)
        db.commit()
        logger.exception("Task failed with exception: %s", e)
        return False

    return False
