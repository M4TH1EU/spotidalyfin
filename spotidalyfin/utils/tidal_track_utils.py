import cachebox
from tidalapi import Track, media
from tidalapi.exceptions import MetadataNotAvailable

from spotidalyfin.cfg import QUALITIES
from spotidalyfin.utils.comparisons import weighted_word_overlap, close
from spotidalyfin.utils.decorators import rate_limit
from spotidalyfin.utils.formatting import format_artists


def get_real_audio_quality(track: Track) -> str:
    """Get the real audio quality of a track."""
    if track.is_DolbyAtmos:
        return "DOLBY_ATMOS"
    elif track.is_Mqa:
        return "MQA"
    elif track.is_HiRes:
        return "HI_RES_LOSSLESS"
    else:
        return track.audio_quality


@cachebox.cached(cachebox.LRUCache(maxsize=64))
@rate_limit
def get_stream(track: Track) -> media.Stream:
    """Get the stream of a track (uses caching)."""
    return track.get_stream()


@cachebox.cached(cachebox.LRUCache(maxsize=32))
def get_lyrics(track: Track) -> str:
    """Get the lyrics of a track (uses caching)."""
    try:
        lyrics = track.lyrics()
        return lyrics.subtitles or lyrics.text
    except MetadataNotAvailable:
        return ""


def get_best_match(tidal_tracks: list[Track], spotify_track: dict) -> Track:
    """
    Get the best match from a list of Tidal tracks based on a Spotify track.

    Uses a scoring system and the real audio quality of the tracks to determine the best match.

    Minimum score to consider a match : 3.5
    Highest quality will be prioritized from score >= 3.5
    If multiple tracks have the same quality, the one with the highest score will be returned.

    :param tidal_tracks: List of Tidal tracks to compare :class:`list[Track]`
    :param spotify_track: Spotify track to compare :class:`dict`

    :return: Best match found on Tidal :class:`Track`
    """

    matches = []
    best_quality = -1

    for track in tidal_tracks:
        track.score = get_track_matching_score(track, spotify_track)
        track.real_quality = get_real_audio_quality(track)
        track.real_quality_score = QUALITIES.get(track.real_quality)
        track.spotify_id = spotify_track.get('id', '')

        if track.score < 3.5:
            continue

        if track.real_quality_score >= best_quality:
            best_quality = QUALITIES.get(track.real_quality)
            matches = track
        elif track.real_quality_score == best_quality:
            matches.append(track)

    if matches and isinstance(matches, list):
        return max(matches, key=lambda x: x.score)
    elif matches and isinstance(matches, Track):
        return matches
    else:
        return tidal_tracks[0]


def get_track_matching_score(track: Track, spotify_track: dict) -> float:
    """
    Calculate the matching score between a Tidal track and a Spotify track.

    The score is calculated based on the following criteria:
    - Duration (1 point)
    - ISRC (0.5 point)
    - Title (1 point)
    - Album name (1.5 point)
    - Artists (1 point)

    Minimum score to consider a match : 3.5
    Maximum score : 5

    :param track: Tidal track to compare :class:`Track`
    :param spotify_track: Spotify track to compare :class:`dict`

    """
    score = 0  # max : 5

    if close(track.duration, spotify_track.get('duration_ms', 0) / 1000):
        score += 1

    if track.isrc.upper() == spotify_track.get('external_ids', {}).get('isrc', '').upper():
        score += 0.5

    if weighted_word_overlap(track.full_name, spotify_track.get('name', '')) > 0.7:
        score += 1

    if weighted_word_overlap(track.album.name, spotify_track.get('album', {}).get('name', '')) > 0.35:
        score += 1.5

    if all(artist in format_artists(track.artists) for artist in
           format_artists(spotify_track.get('artists', []))):
        score += 1

    return score
