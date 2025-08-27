import re
from pathlib import Path

from mutagen.flac import FLAC, Picture
from unidecode import unidecode

from syncphony.constants import MAX_FILENAME_LENGTH
from syncphony.types import Track, ArtistRole, Album
from syncphony.types.manager import Manager
from syncphony.utils.logger import syncphony_logger


def name_builder_artist(media: Track | Album) -> str:
    return " & ".join(artist.name for artist in media.artists)


def name_builder_album_artist(media: Track | Album, first_only: bool = False) -> str:
    artists_tmp: list[str] = []
    artists: list['Artist'] = media.album.artists if isinstance(media, Track) else media.artists

    for artist in artists:
        if ArtistRole.MAIN in artist.roles:
            artists_tmp.append(artist.name)

            if first_only:
                break

    return " & ".join(artists_tmp)


def generate_album_path(album: Album, base_path: Path) -> Path:
    """Generate a sanitized directory path based on album metadata."""
    sanitized_albumartist = unidecode(album.artist.name or "Unknown Artist")
    sanitized_album = unidecode(album.name or "Unknown Album")

    return base_path / sanitized_albumartist / sanitized_album


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for filenames."""
    if not name:
        return "Untitled"
    name = unidecode(name)  # remove accents
    # Replace illegal filesystem characters with hyphen
    name = re.sub(r'[\\/:"*?<>|]', '-', name)
    # Collapse multiple spaces or hyphens
    name = re.sub(r'[\s\-]+', ' ', name).strip()
    # Truncate if too long
    if len(name) > MAX_FILENAME_LENGTH:
        name = name[:MAX_FILENAME_LENGTH].rstrip()
    return name


def generate_track_path(track: Track, base_path: Path) -> Path:
    """Generate a MusicBrainzPicard-style file path based on track metadata."""

    # Choose album artist, fallback to track artist
    album_artist_name = track.album.artist.name if track.album and track.album.artist else track.artist.name
    sanitized_albumartist = sanitize_filename(album_artist_name or "Unknown Artist")

    # Album folder if album artist exists
    sanitized_album = ""
    if track.album and track.album.artist:
        sanitized_album = sanitize_filename(track.album.name or "Unknown Album")

    # Disc number formatting
    disc_number_str = ""
    if getattr(track, "vol_number", None) and getattr(track.album, "num_volumes", None) and track.album.num_volumes > 1:
        if track.album.num_volumes > 9:
            disc_number_str = f"{track.vol_number:02}-"
        else:
            disc_number_str = f"{track.vol_number}-"

    # Track number formatting (2 digits if album artist exists)
    track_number_str = ""
    if track.track_number and track.album and track.album.artist:
        track_number_str = f"{track.track_number:02} "

    # Multi-artist prefix
    multi_artist_prefix = ""
    if hasattr(track, "artists") and len(track.artists) > 1:
        multi_artist_prefix = f"{sanitize_filename(track.artist.name)} - "

    # Track title
    sanitized_title = sanitize_filename(track.name or "Untitled")

    # Build final filename
    filename = f"{disc_number_str}{track_number_str}{multi_artist_prefix}{sanitized_title}".strip()

    # Build full path
    path_parts = [base_path, sanitized_albumartist]
    if sanitized_album:
        path_parts.append(sanitized_album)
    return Path(*path_parts) / filename


def write_metadata(file: Path, track: Track, manager: Manager, fetch_lyrics: bool = False, logger=syncphony_logger):
    if not file.exists():
        logger.error(f"File {file} does not exist, cannot write metadata.")
        return

    if file.suffix.lower() == ".flac":
        audio = FLAC(file)
        audio.clear()  # Clear existing tags

        audio["title"] = track.name or "Untitled"
        audio["tracknumber"] = str(track.track_number or 1)
        audio["discnumber"] = str(track.vol_number or 1)
        audio["totaltracks"] = str(track.album.num_tracks or 1)
        audio["totaldiscs"] = str(track.album.num_volumes or 1)

        audio["artist"] = name_builder_artist(track)
        audio["artists"] = [a.name for a in track.artists]

        audio["album"] = track.album.name or "Unknown Album"
        audio["albumartist"] = name_builder_album_artist(track.album)

        if track.album.barcode:
            audio["barcode"] = track.album.barcode
        if track.album.copyright:
            audio["copyright"] = track.album.copyright

        if track.album.release_date:
            audio["date"] = track.album.release_date.strftime("%Y-%m-%d")
            audio["originaldate"] = track.album.release_date.strftime("%Y-%m-%d")
            audio["originalyear"] = track.album.release_date.strftime("%Y")

        if track.isrc:
            audio["isrc"] = track.isrc

        if track.album.replay_gain:
            audio["replaygain_album_gain"] = str(track.album.replay_gain)
        if track.album.peak_amplitude:
            audio["replaygain_album_peak"] = str(track.album.peak_amplitude)
        if track.replay_gain:
            audio["replaygain_track_gain"] = str(track.replay_gain)
        if track.peak_amplitude:
            audio["replaygain_track_peak"] = str(track.peak_amplitude)

        if track.musicbrainz_recording_id:
            audio["musicbrainz_recordingid"] = track.musicbrainz_recording_id.lower()
        if track.musicbrainz_track_id:
            audio["musicbrainz_trackid"] = track.musicbrainz_track_id.lower()
        if track.musicbrainz_release_artist_id:
            audio["musicbrainz_albumartistid"] = "; ".join(track.musicbrainz_release_artist_id).lower()
        if track.musicbrainz_release_group_id:
            audio["musicbrainz_releasegroupid"] = track.musicbrainz_release_group_id.lower()
        if track.musicbrainz_artist_id:
            audio["musicbrainz_artistid"] = "; ".join(track.musicbrainz_artist_id).lower()
        if track.musicbrainz_release_id:
            audio["musicbrainz_albumid"] = track.musicbrainz_release_id.lower()

        if track.album.country:
            audio["releasecountry"] = track.album.country
        if track.album.release_status:
            audio["releasestatus"] = track.album.release_status

        if fetch_lyrics and manager.supports_lyrics():
            lyrics = manager.get_lyrics(track)
            if lyrics:
                audio["lyrics"] = lyrics

        cover_bytes, cover_mime = manager.get_cover(track)
        if cover_bytes and cover_mime:
            picture = Picture()
            picture.type = 3  # Front cover
            picture.mime = cover_mime
            picture.desc = "front cover"
            picture.data = cover_bytes
            audio.add_picture(picture)

        audio.save()
