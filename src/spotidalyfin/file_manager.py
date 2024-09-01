# file_manager.py
import shutil
from pathlib import Path

from minim.audio import Audio


def format_file_path(metadata):
    def if2(val1, val2):
        return val1 if val1 else val2

    def gt(val1, val2):
        return val1 > val2

    def num(value, digits):
        return f"{value:0{digits}d}"

    albumartist = metadata.get('albumartist', '')
    artist = metadata.get('artist', '')
    album = metadata.get('album', '')
    totaldiscs = metadata.get('totaldiscs', 1)
    discnumber = metadata.get('discnumber', 1)
    tracknumber = metadata.get('tracknumber', None)
    title = metadata.get('title', '')
    multiartist = metadata.get('_multiartist', False)

    result = Path(if2(albumartist, artist))
    if albumartist:
        result /= album

    if gt(totaldiscs, 1):
        result /= f"{num(discnumber, 2) if gt(totaldiscs, 9) else str(discnumber)}-"

    if albumartist and tracknumber:
        if multiartist:
            result /= f"{num(tracknumber, 2)} - {artist} - {title}"
        else:
            result /= f"{num(tracknumber, 2)} - {title}"
    else:
        result /= title

    return result


def organize_track(download_path, final_path):
    files = list(Path(download_path).glob("*"))
    if len(files) != 1:
        print("  Error: More than one file in the download folder.")
        return

    audio_data = Audio(files[0])
    metadata = {
        "albumartist": audio_data.album_artist,
        "artist": audio_data.artist,
        "album": audio_data.album,
        "title": audio_data.title,
        "totaldiscs": audio_data.disc_count,
        "discnumber": audio_data.disc_number,
        "tracknumber": audio_data.track_number,
        "_multiartist": False,
    }

    file_path = format_file_path(metadata).with_suffix(".m4a")
    new_path = Path(final_path) / file_path
    new_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.move(files[0], new_path)
