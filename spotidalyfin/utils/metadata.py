from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import TALB, TCOP, TDRC, TIT2, TOPE, TPE1, TRCK, TSRC, USLT, ID3, APIC
from mutagen.mp3 import MP3
from tidalapi import Track

from spotidalyfin import cfg
from spotidalyfin.utils.file_utils import open_image_url
from spotidalyfin.utils.formatting import not_none, format_artists, num


def get_track_metadata(track: Track) -> dict:
    metadata = dict()
    metadata["title"] = not_none(track.full_name)
    metadata["album"] = not_none(track.album.name)
    metadata["albumartist"] = not_none(track.album.artist.name)
    metadata["artist"] = not_none(", ".join(format_artists(track.artists, lower=False)))
    metadata["copy_right"] = not_none(track.copyright)
    metadata["tracknumber"] = not_none(track.track_num)
    metadata["discnumber"] = not_none(track.volume_num)
    metadata["totaldiscs"] = not_none(track.album.num_volumes, "1")  # TODO: get track with album data
    metadata["totaltracks"] = not_none(track.album.num_tracks, "1")  # TODO: get track with album data
    metadata["date"] = not_none(track.tidal_release_date.strftime("%Y-%m-%d"))
    metadata["isrc"] = not_none(track.isrc)
    metadata["lyrics"] = not_none(track.lyrics)
    metadata["cover_url"] = not_none(track.album.image(1280))
    metadata["cover_data"] = open_image_url(metadata["cover_url"])
    if hasattr(track, "spotify_id"):
        metadata["spotify_id"] = track.spotify_id
    metadata["tidal_id"] = not_none(track.id)
    return metadata


def set_audio_tags(file: Path, metadata: dict):
    if "flac" in file.suffix.lower():
        audio = FLAC(file)
        audio.clear()
        audio["title"] = metadata["title"]
        audio["album"] = metadata["album"]
        audio["albumartist"] = metadata["albumartist"]
        audio["artist"] = metadata["artist"]
        audio["copy_right"] = metadata["copy_right"]
        audio["tracknumber"] = metadata["tracknumber"]
        audio["discnumber"] = metadata["discnumber"]
        audio["totaldiscs"] = metadata["totaldiscs"]
        audio["totaltrack"] = metadata["totaltracks"]
        audio["date"] = metadata["date"]
        audio["isrc"] = metadata["isrc"]
        audio["lyrics"] = metadata["lyrics"]
        if hasattr(metadata, "spotify_id"):
            audio["spotify_id"] = metadata["spotify_id"]
        audio["tidal_id"] = metadata["tidal_id"]

        cover = Picture()
        cover.type = 3
        cover.mime = "image/jpeg" if metadata["cover_url"].endswith(".jpg") else "image/png"
        cover.desc = "front cover"
        cover.data = metadata["cover_data"]
        audio.add_picture(cover)
        audio.save()

    elif "mp3" in file.suffix.lower():
        audio = MP3(file, ID3=ID3)
        audio.clear()
        audio.tags.add(TIT2(encoding=3, text=metadata["title"]))
        audio.tags.add(TALB(encoding=3, text=metadata["album"]))
        audio.tags.add(TPE1(encoding=3, text=metadata["artist"]))
        audio.tags.add(TOPE(encoding=3, text=metadata["albumartist"]))
        audio.tags.add(TCOP(encoding=3, text=metadata["copy_right"]))
        audio.tags.add(TRCK(encoding=3, text=metadata["tracknumber"]))
        audio.tags.add(TRCK(encoding=3, text=metadata["discnumber"]))
        audio.tags.add(TDRC(encoding=3, text=metadata["date"]))
        audio.tags.add(TSRC(encoding=3, text=metadata["isrc"]))
        audio.tags.add(USLT(encoding=3, text=metadata["lyrics"]))
        audio.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=metadata["cover_data"]))
        audio.save()


def format_track_path_from_metadata(metadata: dict, suffix: str = None) -> Path:
    def get_num(value, length=2):
        """Convert value to a zero-padded number string of specified length."""
        return str(value).zfill(length)

    # Extract necessary metadata
    album_artist = metadata.get('albumartist') or metadata.get('artist')
    artist = metadata.get('artist')
    album = metadata.get('album')
    total_discs = num(metadata.get('totaldiscs'))
    disc_number = num(metadata.get('discnumber'))
    track_number = num(metadata.get('tracknumber'))
    title = metadata.get('title')
    multiartist = metadata.get('_multiartist')

    invalid_chars = ["<", ">", ":", "\"", "/", "\\", "|", "?", "*", "."]
    for char in invalid_chars:
        title = title.replace(char, "")
        album_artist = album_artist.replace(char, "")
        artist = artist.replace(char, "")
        album = album.replace(char, "")

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

    if not suffix:
        suffix = ".flac" if cfg.get("m4a2flac") else ".m4a"
    path += suffix

    return Path(path)
