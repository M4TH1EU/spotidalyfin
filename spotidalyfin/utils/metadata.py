import shutil
from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import TALB, TCOM, TCOP, TDRC, TIT2, TOPE, TPE1, TRCK, TSRC, USLT, ID3, APIC
from mutagen.mp3 import MP3
from tidalapi import Track

from spotidalyfin.utils.file_utils import open_image_url
from spotidalyfin.utils.formatting import not_none, format_artists, num
from spotidalyfin.utils.logger import log
from spotidalyfin.utils.tidal_track_utils import get_lyrics


def set_audio_tags(file: Path, track: Track) -> dict:
    title = not_none(track.full_name)
    album = not_none(track.album.name)
    albumartist = not_none(track.album.artist.name)
    artists = not_none(", ".join(format_artists(track.artists, lower=False)))
    copy_right = not_none(track.copyright)
    tracknumber = not_none(track.track_num)
    discnumber = not_none(track.volume_num)
    totaldisc = not_none(None)
    totaltrack = not_none(track.album.num_tracks)  # TODO: get track with album data
    date = not_none(track.tidal_release_date.strftime("%Y-%m-%d"))
    composer = not_none(None)
    isrc = not_none(track.isrc)
    lyrics = not_none(get_lyrics(track))
    cover_url = not_none(track.album.image())
    cover_data = open_image_url(cover_url)

    if "flac" in file.suffix.lower():
        audio = FLAC(file)
        audio.clear()
        audio["title"] = title
        audio["album"] = album
        audio["albumartist"] = albumartist
        audio["artist"] = artists
        audio["copy_right"] = copy_right
        audio["tracknumber"] = tracknumber
        audio["discnumber"] = discnumber
        audio["totaldisc"] = totaldisc
        audio["totaltrack"] = totaltrack
        audio["date"] = date
        audio["composer"] = composer
        audio["isrc"] = isrc
        audio["lyrics"] = lyrics
        if hasattr(track, "spotify_id"):
            audio["spotify_id"] = track.spotify_id
        audio["tidal_id"] = not_none(track.id)

        cover = Picture()
        cover.type = 3
        cover.mime = "image/jpeg" if cover_url.endswith(".jpg") else "image/png"
        cover.desc = "front cover"
        cover.data = cover_data
        audio.add_picture(cover)
        audio.save()

    elif "mp3" in file.suffix.lower():
        audio = MP3(file, ID3=ID3)
        audio.clear()
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TALB(encoding=3, text=album))
        audio.tags.add(TPE1(encoding=3, text=artists))
        audio.tags.add(TOPE(encoding=3, text=albumartist))
        audio.tags.add(TCOP(encoding=3, text=copy_right))
        audio.tags.add(TRCK(encoding=3, text=tracknumber))
        audio.tags.add(TRCK(encoding=3, text=discnumber))
        audio.tags.add(TDRC(encoding=3, text=date))
        audio.tags.add(TCOM(encoding=3, text=composer))
        audio.tags.add(TSRC(encoding=3, text=isrc))
        audio.tags.add(USLT(encoding=3, text=lyrics))
        audio.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_data))
        audio.save()

    return {"albumartist": albumartist, "artist": artists, "album": album, "title": title, "totaldiscs": totaldisc,
            "discnumber": discnumber, "tracknumber": tracknumber, "_multiartist": False}


def organize_audio_file(file_path: Path, output_dir, metadata: dict):
    """Organize a single audio file based on its metadata."""
    if file_path.exists() and file_path.is_file():
        path = format_track_path_from_metadata(metadata=metadata, file_path=file_path)
        if path:
            destination = output_dir / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(file_path, destination)
            log.debug(f"Moved {file_path} to {destination}")


def format_track_path_from_metadata(metadata: dict, file_path: Path) -> str:
    def get_num(value, length=2):
        """Convert value to a zero-padded number string of specified length."""
        return str(value).zfill(length)

    if None in metadata.values():
        log.error(f"Missing metadata for {file_path}.")
        return ""

    # Extract necessary metadata
    album_artist = metadata.get('albumartist') or metadata.get('artist')
    artist = metadata.get('artist')
    album = metadata.get('album')
    total_discs = num(metadata.get('totaldiscs'))
    disc_number = num(metadata.get('discnumber'))
    track_number = num(metadata.get('tracknumber'))
    title = metadata.get('title')
    multiartist = metadata.get('_multiartist')

    # Build path components
    path = f"{album_artist}/"

    if album_artist and album:
        path += f"{album}/"

    if total_discs > 1:
        disc_part = f"{get_num(disc_number)}-" if total_discs > 9 else f"{disc_number}-"
        path += disc_part

    if album_artist and track_number:
        path += f"{get_num(track_number)} "

    if multiartist and artist:
        path += f"{artist} - "

    path += f"{title}"
    path += file_path.suffix

    return path
