import re
from typing import Optional

from rapidfuzz import fuzz, utils

from syncphony.types import Track, TrackQuality, Album


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

def normalize_album_name(name: str, remove_words_with_apostrophes: bool = False) -> str:
    """
    Normalizes album name by:
    - Lowercasing
    - Keep only alphanumeric characters and spaces
    - Removing extra whitespace and punctuation
    - Optional: removing words with apostrophes (e.g., "Don't", "It's"), mostly for Jellyfin compatibility
    """
    name = name.lower()

    if remove_words_with_apostrophes:
        name = re.sub(r"\b\w*'\w*\b", '', name)

    name = re.sub(r'[^\w\s]', '', name)
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

        weight_total += 0.25

    # Normalize score
    if weight_total == 0:
        return 0.0

    return round(score / weight_total, 2)


def compare_albums(album1: Album, album2: Album) -> float:
    score = 0.0
    weight_total = 0.0

    # 1. UPC (high confidence if available)
    if album1.barcode and album2.barcode:
        if album1.barcode == album2.barcode:
            return 100.0  # UPC match is a definitive match
        else:
            weight_total += 0.2

    # 2. Name
    name_score = compare_strings_set_ratio(album1.name, album2.name)
    score += name_score * 0.4
    weight_total += 0.4

    # 3. Artist name
    artist_score = compare_strings_set_ratio(album1.artist.name, album2.artist.name)
    score += artist_score * 0.25
    weight_total += 0.25

    # 4. Release date (if available)
    if album1.release_date and album2.release_date:
        if album1.release_date.year == album2.release_date.year:
            score += 100 * 0.15
        weight_total += 0.15

    # 5. Track count (if available)
    if album1.num_tracks and album2.num_tracks:
        if album1.num_tracks == album2.num_tracks:
            score += 100 * 0.2
        weight_total += 0.2

    # 6. Duration (if available)
    if album1.duration and album2.duration:
        duration_diff = abs(album1.duration - album2.duration)
        if duration_diff <= 5:
            score += 100 * 0.1
        elif duration_diff <= 15:
            score += 75 * 0.1
        elif duration_diff <= 30:
            score += 50 * 0.1
        weight_total += 0.1

    # 7. Number of volumes (if available)
    if album1.num_volumes and album2.num_volumes:
        if album1.num_volumes == album2.num_volumes:
            score += 100 * 0.1
        weight_total += 0.1

    # Normalize score
    if weight_total == 0:
        return 0.0

    return round(score / weight_total, 2)


#
# def compare_acoustid_track(recording: dict, track: Track):
#     score = 0.0
#     weight_total = 0.0
#
#     # 1. Name
#     name_score = compare_strings(track.name, recording.get('title', ''))
#     score += name_score * 0.3
#     weight_total += 0.3
#
#     # 2. Artist name
#     artist_score = compare_strings(track.artist.name,
#                                    recording.get('artists', [{}])[0].get('name', ''))
#     score += artist_score * 0.25
#     weight_total += 0.25
#
#     # 3. Duration (in seconds, allow small delta)
#     if track.duration:
#         duration_diff = abs(track.duration - recording.get('duration', 0))
#         if duration_diff <= 2:
#             score += 100 * 0.2
#         elif duration_diff <= 5:
#             score += 75 * 0.2
#         elif duration_diff <= 10:
#             score += 50 * 0.2
#         weight_total += 0.2
#
#     # Normalize score
#     if weight_total == 0:
#         return 0.0
#
#     return round(score / weight_total, 2)

#
# def compare_musicbrainz_release_track(release: dict, track: Track):
#     score = 0.0
#     weight_total = 0.0
#
#     # 1. Album Name
#     name_score = compare_strings(track.album.name, release.get('title', ''))
#     score += name_score * 0.3
#     weight_total += 0.3
#
#     # 2. Artist name
#     artist_score = compare_strings(track.artist.name,
#                                    release.get('artist-credit', [{}])[0].get('artist', {}).get('name', ''))
#     score += artist_score * 0.25
#     weight_total += 0.25
#
#     # 3. Release date (if available)
#     if track.album.release_date and 'date' in release:
#         release_date = release.get('date', '')
#         if release_date:
#             # Compare only the year for simplicity
#             if track.album.release_date.year == release_date[:4]:
#                 score += 100 * 0.25
#             weight_total += 0.25
#
#     # 4. Barcode (if available)
#     if track.album.barcode and 'barcode' in release:
#         # Compare barcode if available
#         if track.album.barcode == release.get('barcode', ''):
#             score += 100 * 0.25
#         weight_total += 0.25
#
#     # 5. Track number (if available)
#     if track.album.num_tracks and release.get('medium-count') > 0:
#         track_number = release.get('medium-list')[0].get('track-list', [])[0].get('position', 0)
#         if track.track_number == track_number:
#             score += 100 * 0.25
#
#         weight_total += 0.25
#
#     # 6. Track count (if available)
#     if track.album.num_tracks and release.get('medium-count') > 0:
#         track_num = release.get('medium-list')[0].get('track-count', 0)
#         if track.album.num_tracks == track_num:
#             score += 100 * 0.25
#         weight_total += 0.25
#
#     # Normalize score
#     if weight_total == 0:
#         return 0.0
#
#     return round(score / weight_total, 2)


def compare_musicbrainz_release_album(release: dict, album: Album):
    score = 0.0
    weight_total = 0.0

    # 1. Album Name
    name_score = compare_strings(album.name, release.get('title', ''))
    score += name_score * 0.3
    weight_total += 0.3

    # 2. Artist name
    artist_score = compare_strings(album.artist.name,
                                   release.get('artist-credit', [{}])[0].get('artist', {}).get('name', ''))
    score += artist_score * 0.25
    weight_total += 0.25

    # 3 Artists
    if album.artists and 'artist-credit' in release:
        for artist in album.artists:
            if any(compare_strings(artist.name, ac.get('artist', {}).get('name', '')) > 80 for ac in release['artist-credit'] if isinstance(ac, dict)):
                score += 100 * 0.25
                weight_total += 0.25
                break

    # 3. Release date (if available)
    if album.release_date and 'date' in release:
        release_date = release.get('date', '')
        if release_date:
            if album.release_date.year == release_date[:4]:
                score += 100 * 0.15
            if album.release_date.month and len(release_date) >= 7 and album.release_date.month == int(
                    release_date[5:7]):
                score += 75 * 0.15
                weight_total += 0.15
            if album.release_date.day and len(release_date) == 10 and album.release_date.day == int(release_date[8:10]):
                score += 50 * 0.15
                weight_total += 0.15

            weight_total += 0.15

    # 4. Barcode (if available)
    if album.barcode and 'barcode' in release:
        # Compare barcode if available
        if album.barcode == release.get('barcode', ''):
            score += 100 * 0.3
        elif album.barcode.lstrip("00") == release.get('barcode', '').lstrip(
                "00"):  # sometimes barcodes have 00 in front
            score += 100 * 0.3

        weight_total += 0.3

    # 5. Track count (if available)
    if album.num_tracks and release.get('medium-track-count') > 0:
        if album.num_tracks == release.get('medium-track-count'):
            score += 100 * 0.2
        weight_total += 0.2

    return round(score / weight_total, 2)
