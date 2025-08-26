from pathlib import Path

import acoustid
import musicbrainzngs

from syncphony.types import Album, Track
from syncphony.types.compare import compare_musicbrainz_release_album, compare_strings


def acoustic_id_lookup(file: Path):
    duration, fingerprint = acoustid.fingerprint_file(file)
    acoustid_res: dict = acoustid.lookup("YjwCJxwC0r", fingerprint, duration)
    return acoustid_res


def match_album_to_musicbrainz(album: Album, tries=0) -> dict | None:
    try:
        if tries == 0:
            result = musicbrainzngs.search_releases(
                barcode=album.barcode if album.barcode else None,
                date=album.release_date.year if album.release_date else None,
                status="official",
                limit=5,
            )
        elif tries == 1:
            result = musicbrainzngs.search_releases(
                artist=album.artist,
                release=album.name,
                barcode=album.barcode if album.barcode else None,
                date=album.release_date.year if album.release_date else None,
                status="official",
                limit=5,
            )
        elif tries == 2:
            result = musicbrainzngs.search_releases(
                artist=album.artist,
                release=album.name,
                barcode=album.barcode if album.barcode else None,
                status="official",
                limit=5,
            )
        else:
            return None

        release_list = result.get("release-list", [])
        scored_releases_list = [(r, compare_musicbrainz_release_album(r, album)) for r in release_list]
        best_release, best_release_score = max(scored_releases_list, key=lambda x: x[1], default=(None, 0))
        if best_release and best_release_score >= 85.0:
            return best_release
        elif tries < 3:
            return match_album_to_musicbrainz(album, tries=tries + 1)
        else:
            return None

    except Exception as e:
        print(f"Error searching for album {album.name} by {album.artist}: {e}")
        return None


def get_tracks_from_release_id(release_id: str) -> list[dict] | None:
    try:
        result = musicbrainzngs.get_release_by_id(release_id, includes=["recordings"])
        track_list = result["release"]["medium-list"][0]["track-list"]
        return track_list
    except Exception as e:
        print(f"Error getting tracks for release ID {release_id}: {e}")
        return None


def find_track_in_release_tracklist(track: Track, track_list: list[dict]) -> dict | None:
    if track.track_number is not None:
        for t in track_list:
            if int(t.get("position", -1)) == track.track_number:
                return t
    if track.name:
        for t in track_list:
            if compare_strings(t.get("recording", {}).get("title", ""), track.name) >= 90.0 and abs(
                    int(t.get("length", 0)) / 1000 - (track.duration or 0)) < 6:
                return t
    return None


def get_track_from_recording_id(recording_id: str) -> dict | None:
    try:
        result = musicbrainzngs.get_recording_by_id(id=recording_id, includes=["releases", "artists"])
        recording = result["recording"]
        return recording
    except Exception as e:
        print(f"Error getting recording for recording ID {recording_id}: {e}")
        return None
