from pathlib import Path

import acoustid
import musicbrainzngs

from syncphony.types import Album, Track
from syncphony.utils.compare import compare_musicbrainz_release_album, compare_strings, normalize_album_name
from syncphony.utils.logger import syncphony_logger


def enrich_album_with_musicbrainz(album, logger=syncphony_logger):
    """Enrich album and its tracks with MusicBrainz data."""

    # Step 1: Match album to MusicBrainz
    mbz_release = match_album_to_musicbrainz(album, logger=logger)
    if not mbz_release:
        logger.warning(f"No MusicBrainz match found for album: {album.name} by {album.artist.name}")
        return  # nothing to enrich

    mbz_release_id = mbz_release.get("id")
    album.country = mbz_release.get("country")
    album.release_status = mbz_release.get("status")

    # Step 2: Fetch release tracks once
    mbz_release_tracks = get_tracks_from_release_id(mbz_release_id, logger) or []
    if not mbz_release_tracks:
        logger.warning(
            f"No tracks found for MusicBrainz release ID: {mbz_release_id} for album: {album.name} by {album.artist.name}")

    # Step 3: Build a helper to extract artist IDs
    def extract_artist_ids(item, key="artist-credit"):
        return [
            artist.get("artist", {}).get("id")
            for artist in item.get(key, [])
            if isinstance(artist, dict)
        ]

    # Step 4: Enrich each track
    for track in album.tracks:
        logger.debug(f"Enriching track: {track.name} by {track.artist.name} from album: {album.name}")

        track.musicbrainz_release_id = mbz_release_id
        track.musicbrainz_release_artist_id = extract_artist_ids(mbz_release)
        track.musicbrainz_release_group_id = mbz_release.get("release-group", {}).get("id")

        if not mbz_release_tracks:
            continue

        mbz_track = find_track_in_release_tracklist(track, mbz_release_tracks, logger=logger)
        if not mbz_track:
            logger.warning(
                f"No matching track found in MusicBrainz release ({mbz_release_id}) for track: {track.name} by {track.artist.name} in album: {album.name}")
            continue

        # Track-specific MB data
        track.musicbrainz_track_id = mbz_track.get("id")
        recording = mbz_track.get("recording", {})
        track.musicbrainz_recording_id = recording.get("id")

        # Fetch recording details for artist IDs
        if recording.get("id"):
            mbz_track_detail = get_track_from_recording_id(recording["id"], logger=logger)
            if mbz_track_detail:
                track.musicbrainz_artist_id = extract_artist_ids(mbz_track_detail)
            else:
                logger.warning(
                    f"Failed to fetch recording details for recording ID: {recording['id']} for track: {track.name} by {track.artist.name}")
        else:
            logger.warning(
                f"No recording ID found for track: {track.name} by {track.artist.name} in MusicBrainz track data")


def acoustic_id_lookup(file: Path):
    duration, fingerprint = acoustid.fingerprint_file(file)
    acoustid_res: dict = acoustid.lookup("YjwCJxwC0r", fingerprint, duration)
    return acoustid_res


def match_album_to_musicbrainz(album: Album, logger=syncphony_logger, tries=0) -> dict | None:
    try:
        if tries == 0:
            result = musicbrainzngs.search_releases(
                barcode=album.barcode if album.barcode else None,
                date=album.release_date.year if album.release_date else None,
                status="official",
                limit=3
            )
        elif tries == 1:
            result = musicbrainzngs.search_releases(
                query=normalize_album_name(album.name),
                artist=album.artist.name,
                barcode=album.barcode if album.barcode else None,
                date=album.release_date.year if album.release_date else None,
                status="official",
                limit=7
            )
        elif tries == 2:
            result = musicbrainzngs.search_releases(
                query=album.name,
                limit=10,
            )
        else:
            return None

        release_list = result.get("release-list", [])
        scored_releases_list = [(r, compare_musicbrainz_release_album(r, album)) for r in release_list]
        best_release, best_release_score = max(scored_releases_list, key=lambda x: x[1], default=(None, 0))
        if best_release and best_release_score >= 85.0:
            return best_release
        elif tries < 3:
            return match_album_to_musicbrainz(album, tries=tries + 1, logger=logger)
        else:
            return None

    except Exception as e:
        logger.error(f"Exception during MusicBrainz search for album {album.name} by {album.artist.name}: {e}")
        return None


def get_tracks_from_release_id(release_id: str, logger=syncphony_logger) -> list[dict] | None:
    try:
        result = musicbrainzngs.get_release_by_id(release_id, includes=["recordings"])
        track_list = result["release"]["medium-list"][0]["track-list"]
        return track_list
    except Exception as e:
        logger.error(f"Error getting tracks for release ID {release_id}: {e}")
        return None


def find_track_in_release_tracklist(track: Track, track_list: list[dict], logger=syncphony_logger) -> dict | None:
    if track.track_number is not None:
        for t in track_list:
            if int(t.get("position", -1)) == track.track_number:
                return t
    if track.name:
        for t in track_list:
            if compare_strings(t.get("recording", {}).get("title", ""), track.name) >= 90.0 and abs(
                    int(t.get("length", 0)) / 1000 - (track.duration or 0)) < 6:
                return t

    logger.warning(f"No matching track found for {track.name} in provided track list.")
    return None


def get_track_from_recording_id(recording_id: str, logger=syncphony_logger) -> dict | None:
    try:
        result = musicbrainzngs.get_recording_by_id(id=recording_id, includes=["releases", "artists"])
        recording = result["recording"]
        return recording
    except Exception as e:
        logger.error(f"Error getting track from recording ID {recording_id}: {e}")
        return None
