from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import acoustid
import musicbrainzngs

from syncphony.models import Track
from syncphony.models.compare import compare_acoustid_track, compare_strings, compare_musicbrainz_release_track
from syncphony.utils.logger import log


@dataclass
class TrackWithMetadata:
    track: Track
    acoustid: str = ""
    musicbrainz: dict = field(default_factory=dict)


def _parse_musicbrainz_data(recording: dict, release: dict, acoustid_id: str = None) -> dict:
    return {
        "genre": [tag['name'] for tag in recording.get('tag-list', [])],
        "musicbrainz_artistid": recording.get("artist-credit", [{}])[0].get(
            "artist", {}).get("id"),
        "musicbrainz_trackid": recording.get("id"),
        "musicbrainz_albumartistid": release.get("artist-credit", [{}])[
            0].get("artist", {}).get("id"),
        "musicbrainz_albumid": release.get(
            "id"),
        "date": release.get("date"),
        "originaldate": release.get("date"),
        "originalyear": release.get("date")[:4],
        "barcode": release.get("barcode"),
        "releasecountry": release.get("country"),
        "acoustid_id": acoustid_id
    }


def process_metadata(track: Track, tempfile_path: Path) -> Optional[TrackWithMetadata]:
    # Retrieve AcoustID fingerprint and lookup basic metadata
    duration, fingerprint = acoustid.fingerprint_file(tempfile_path)
    acoustid_res: dict = acoustid.lookup("YjwCJxwC0r", fingerprint,
                                         duration)  # public key for testing, please don't abuse
    musicbrainz_data = {}
    musicbrainzngs.set_useragent("syncphony", "0.1")

    if acoustid_res.get('results'):
        if len(acoustid_res.get('results')) >= 1:
            scored_results: list[tuple[dict, float, str]] = []

            for result in acoustid_res.get('results'):
                if result.get('recordings') and len(result.get('recordings')) > 0:
                    scored_results = [(r, compare_acoustid_track(r, track), result.get('id')) for r in
                                      result.get('recordings')]

            best_match, best_score, acoustid_id = max(scored_results, key=lambda x: x[1], default=(None, 0))
            if best_match and best_score >= 75.0:
                # Found a good match, proceed with MusicBrainz query
                try:
                    musicbrainz_res: dict = musicbrainzngs.get_recording_by_id(
                        best_match.get('id'),
                        includes=["artists", "releases", "isrcs", "tags", "discids"],
                        release_status=['official'],
                        release_type=['album', 'single']
                    )
                    recording = musicbrainz_res.get("recording", {})
                    scored_releases_list = [(r, compare_musicbrainz_release_track(r, track)) for r in
                                            recording.get("release-list", [])]
                    best_release, best_release_score = max(scored_releases_list, key=lambda x: x[1], default=(None, 0))

                    musicbrainz_data = _parse_musicbrainz_data(recording, best_release, acoustid_id)

                except Exception as e:
                    log.warning(f"No results found for AcoustID {best_match.get('id')} on MusicBrainz: {e}")

    if not musicbrainz_data and track.isrc:
        log.debug(f"No results found for AcoustID for {track.name} by {track.artist.name}")

        # If no AcoustID results, try MusicBrainz by ISRC
        try:
            musicbrainz_res: dict = musicbrainzngs.get_recordings_by_isrc(track.isrc, includes=["artists", "releases"])
            for recording in musicbrainz_res.get("isrc", {}).get("recording-list", []):
                title = recording.get('title', '')
                artist_name = recording.get('artist-credit', [{}])[0].get('artist', {}).get('name', '')

                # Make sure that the ISRC result is a good match
                if (compare_strings(title, track.name) >= 75.0 and
                        compare_strings(artist_name, track.artist.name >= 75.0)):
                    recording = musicbrainz_res.get("recording", {})
                    musicbrainz_data = _parse_musicbrainz_data(recording, recording.get("release-list", [{}])[0],
                                                               track.isrc)
                    break


        except Exception as e:
            log.warning(f"No results found for ISRC {track.isrc} on MusicBrainz: {e}")

    log.info(musicbrainz_data)
