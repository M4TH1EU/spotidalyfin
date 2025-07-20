import re
from typing import Optional

from rapidfuzz import fuzz, utils

from spotidalyfin.models import Track, TrackQuality, Artist


def normalize_track_name(name: str) -> str:
    """
    Normalizes track name by:
    - Removing dash/parentheses-based suffixes like ' - 2019 Remaster'
    - Replacing parentheses with dashes for consistency
    - Lowercasing
    - Removing extra whitespace and punctuation
    """
    name = name.lower()
    name = name.replace('–', '-')
    name = re.sub(r'\s*[\(\[]?(remaster(ed)?|mono|version|mix|live|edit|explicit|radio edit)[^\)\]]*[\)\]]?', '', name,
                  flags=re.IGNORECASE)
    name = re.sub(r'[-–]\s*\d{4}', '', name)  # Remove years like '- 2019'
    name = re.sub(r'[^\w\s]', '', name)  # Remove punctuation
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def compare_strings(s1: Optional[str], s2: Optional[str]) -> float:
    if not s1 or not s2:
        return 0.0
    return fuzz.token_set_ratio(s1, s2, processor=utils.default_process)


def compare_tracks(track1: Track, track2: Track, use_track2_quality_as_criteria: bool = False) -> float:
    score = 0.0
    weight_total = 0.0

    # 1. ISRC (high confidence if available)
    if track1.isrc and track2.isrc:
        if track1.isrc == track2.isrc:
            return 100.0  # ISRC match is a definitive match
        else:
            return 0.0  # Conflicting ISRCs are assumed different

    # 2. Name
    name_score = compare_strings(track1.name, track2.name)
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
    artist_score = compare_strings(track1.artist.name, track2.artist.name)
    score += artist_score * 0.25
    weight_total += 0.25

    # 5. Album name
    album_score = compare_strings(track1.album.name, track2.album.name)
    score += album_score * 0.15
    weight_total += 0.15

    # 6. Album artist
    if track1.album.artist and track2.album.artist:
        album_artist_score = compare_strings(track1.album.artist.name, track2.album.artist.name)
        score += album_artist_score * 0.1
        weight_total += 0.1

    # 7. Quality (if applicable)
    if use_track2_quality_as_criteria and track2.quality:
        if track2.quality == TrackQuality.HI_RES_LOSSLESS:
            score += 100 * 0.25
        elif track2.quality == TrackQuality.LOSSLESS:
            score += 75 * 0.25
        elif track2.quality == TrackQuality.LOW:
            score += 0

        weight_total += 0.25

    # Normalize score
    if weight_total == 0:
        return 0.0

    return round(score / weight_total, 2)


# def compare_artists(artist1: Artist, artist2: Artist) -> float:
#     """
#     Compare two artists based on their names.
#     """
#     if not artist1 or not artist2:
#         return 0.0
#
#     return compare_strings(artist1.name, artist2.name)
