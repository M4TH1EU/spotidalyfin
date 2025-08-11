import re
from typing import Optional

from rapidfuzz import fuzz, utils

from syncphony.models import Track, TrackQuality


def normalize_track_name(name: str, remove_words_with_apostrophes: bool = False) -> str:
    """
    Normalizes track name by:
    - Removing dash/parentheses-based suffixes like ' - 2019 Remaster'
    - Replacing parentheses with dashes for consistency
    - Lowercasing
    - Removing extra whitespace and punctuation
    - Remove '/' and '\' characters
    - Optional: removing words with apostrophes (e.g., "Don't", "It's"), mostly for Jellyfin compatibility
    """
    name = name.lower()

    if remove_words_with_apostrophes:
        name = re.sub(r'\b\w*\'\w*\b', '', name)

    name = name.replace('–', '-')
    name = re.sub(r'\s*[\(\[]?(remaster(ed)?|mono|version|mix|live|edit|explicit|radio edit)[^\)\]]*[\)\]]?', '', name,
                  flags=re.IGNORECASE)
    name = re.sub(r'[-–]\s*\d{4}', '', name)  # Remove years like '- 2019'
    name = name.replace('/', ' ').replace('\\', ' ')  # Remove slashes
    name = re.sub(r'[^\w\s]', '', name)  # Remove punctuation
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def normalize_artist_name(name: str, remove_words_with_double_quote: bool = False) -> str:
    """
    Normalizes artist name by:
    - Lowercasing
    - Removing extra whitespace and punctuation
    - Replacing '&' with 'and'
    - Replacing single quotes with curly apostrophes
    """
    name = name.lower()

    if remove_words_with_double_quote:
        name = re.sub(r'\s*"\w+"\s*', ' ', name)

    name = re.sub(r'[^\w\s]', '', name)  # Remove punctuation
    name = re.sub(r'\s+', ' ', name).strip()  # Remove extra whitespace
    name = re.sub('& ', 'and ', name)  # Replace '&' with 'and')
    name = re.sub('\'', '’', name)  # Replace single quotes with curly apostrophes

    return name


def compare_strings_set_ratio(s1: Optional[str], s2: Optional[str]) -> float:
    if not s1 or not s2:
        return 0.0
    return fuzz.token_set_ratio(s1, s2, processor=utils.default_process)


def compare_strings(s1: Optional[str], s2: Optional[str]) -> float:
    if not s1 or not s2:
        return 0.0
    return fuzz.ratio(s1, s2, processor=utils.default_process)


def compare_tracks(track1: Track, track2: Track, use_track2_quality_as_criteria: bool = False) -> float:
    score = 0.0
    weight_total = 0.0

    # 1. ISRC (high confidence if available)
    if track1.isrc and track2.isrc:
        if track1.isrc == track2.isrc:
            return 100.0  # ISRC match is a definitive match
        else:
            score += 0
            weight_total += 0.1

    # 2. Name
    name_score = compare_strings_set_ratio(track1.name, track2.name)
    score += name_score * 0.3
    weight_total += 0.3

    # 3. Duration (in seconds, allow small delta)
    if track1.duration and track2.duration:
        duration_diff = abs(track1.duration - track2.duration)
        if duration_diff <= 2:
            score += 100 * 0.2
        elif duration_diff <= 5:
            score += 75 * 0.2
        elif duration_diff <= 10:
            score += 50 * 0.2
        else:
            score += 0
        weight_total += 0.2

    # 4. Artist name
    artist_score = compare_strings_set_ratio(track1.artist.name, track2.artist.name)
    score += artist_score * 0.25
    weight_total += 0.25

    # 5. Album name
    album_score = compare_strings_set_ratio(track1.album.name, track2.album.name)
    score += album_score * 0.15
    weight_total += 0.15

    # 6. Album artist
    if track1.album.artist and track2.album.artist:
        album_artist_score = compare_strings_set_ratio(track1.album.artist.name, track2.album.artist.name)
        score += album_artist_score * 0.1
        weight_total += 0.1

    # 7. Quality (if applicable)
    if use_track2_quality_as_criteria and track2.quality:
        if track2.quality == TrackQuality.EXTREME:
            score += 100 * 0.25
        elif track2.quality == TrackQuality.HIGH:
            score += 75 * 0.25
        elif track2.quality == TrackQuality.MEDIUM:
            score += 25 * 0.25
        else:
            score += 0

        weight_total += 0.25

    # Normalize score
    if weight_total == 0:
        return 0.0

    return round(score / weight_total, 2)


def compare_acoustid_track(recording: dict, track: Track):
    score = 0.0
    weight_total = 0.0

    # 1. Name
    name_score = compare_strings(track.name, recording.get('title', ''))
    score += name_score * 0.3
    weight_total += 0.3

    # 2. Artist name
    artist_score = compare_strings(track.artist.name,
                                   recording.get('artists', [{}])[0].get('name', ''))
    score += artist_score * 0.25
    weight_total += 0.25

    # 3. Duration (in seconds, allow small delta)
    if track.duration:
        duration_diff = abs(track.duration - recording.get('duration', 0))
        if duration_diff <= 2:
            score += 100 * 0.2
        elif duration_diff <= 5:
            score += 75 * 0.2
        elif duration_diff <= 10:
            score += 50 * 0.2
        else:
            score += 0
        weight_total += 0.2

    # Normalize score
    if weight_total == 0:
        return 0.0

    return round(score / weight_total, 2)


def compare_musicbrainz_release_track(release: dict, track: Track):
    score = 0.0
    weight_total = 0.0

    # 1. Name
    name_score = compare_strings(track.name, release.get('title', ''))
    score += name_score * 0.3
    weight_total += 0.3

    # 2. Artist name
    artist_score = compare_strings(track.artist.name,
                                   release.get('artist-credit', [{}])[0].get('artist', {}).get('name', ''))
    score += artist_score * 0.25
    weight_total += 0.25

    # 3. Duration (in seconds, allow small delta)
    if track.duration:
        duration_diff = abs(track.duration - release.get('length', 0) / 1000)  # length is in milliseconds
        if duration_diff <= 2:
            score += 100 * 0.2
        elif duration_diff <= 5:
            score += 75 * 0.2
        elif duration_diff <= 10:
            score += 50 * 0.2
        else:
            score += 0
        weight_total += 0.2

    # Normalize score
    if weight_total == 0:
        return 0.0

    return round(score / weight_total, 2)
