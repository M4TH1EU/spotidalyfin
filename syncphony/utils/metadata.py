from pathlib import Path

from mutagen.flac import FLAC, Picture
from unidecode import unidecode

from syncphony.types import Track, ArtistRole, Album
from syncphony.types.manager import Manager
from syncphony.utils.logger import log


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


def generate_path(track: Track, base_path: Path, extension: str = "flac") -> Path:
    """Generate a sanitized file path based on metadata."""
    # Format track number with leading zeros
    track_number_str = f"{int(track.track_number):02}" if track.track_number else "00"

    sanitized_albumartist = unidecode(track.album.artist.name or "Unknown Artist")
    sanitized_album = unidecode(track.album.name or "Unknown Album")
    sanitized_title = unidecode(track.name or "Untitled")

    return base_path / sanitized_albumartist / sanitized_album / f"{track_number_str} - {sanitized_title}.{extension.lstrip('.')}"


def write_metadata(file: Path, track: Track, manager: Manager, fetch_lyrics: bool = False):
    if not file.exists():
        log.error(f"File {file} does not exist, cannot write metadata.")
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
