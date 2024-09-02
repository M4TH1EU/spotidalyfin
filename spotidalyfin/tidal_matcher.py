import random
import time
from difflib import SequenceMatcher

from future.backports.datetime import datetime
from minim.tidal import API

from spotidalyfin import constants


def format_string(string: str) -> str:
    """
    Format a string by removing content after certain delimiters and stripping whitespace.

    Args:
        string (str): The string to format.

    Returns:
        str: Formatted string.
    """
    return string.split('-')[0].strip().split('(')[0].strip().split('[')[0].strip()


def format_artists(artists: list) -> list:
    """
    Format a list of artist names by handling multiple separators and converting to lowercase.

    Args:
        artists (list): List of artist names or dictionaries containing artist information.

    Returns:
        list: Formatted list of artist names in lowercase.
    """
    formatted_artists = []
    for artist in artists:
        if isinstance(artist, dict):
            artist = artist.get('name', '')

        separators = ['&', 'and', ',']
        for sep in separators:
            if sep in artist:
                artist = artist.split(sep)
                break

        if isinstance(artist, list):
            formatted_artists.extend(a.strip().lower() for a in artist)
        else:
            formatted_artists.append(artist.strip().lower())

    return formatted_artists


def similar(a: str, b: str, ratio: float = 0.9) -> bool:
    """
    Check if two strings are similar based on a ratio threshold.

    Args:
        a (str): First string.
        b (str): Second string.
        ratio (float): Similarity ratio threshold.

    Returns:
        bool: True if strings are similar, False otherwise.
    """
    return SequenceMatcher(None, a, b).ratio() > ratio


def close(a: int, b: int, delta: int = 2) -> bool:
    """
    Check if two numbers are within a specified range.

    Args:
        a (int): First number.
        b (int): Second number.
        delta (int): Maximum allowed difference.

    Returns:
        bool: True if numbers are within the delta range, False otherwise.
    """
    return abs(a - b) < delta


def parse_date(date_str: str):
    """
    Parse a date string into a datetime object.

    Args:
        date_str (str): The date string.

    Returns:
        datetime or None: Parsed datetime object or None if format is unrecognized.
    """
    formats = {
        4: '%Y',
        7: '%Y-%m',
        10: '%Y-%m-%d'
    }
    date_format = formats.get(len(date_str))
    return datetime.strptime(date_str, date_format) if date_format else None


def match_song(tidal_track: dict, spotify_track: dict) -> bool:
    """
    Match a Tidal track against a Spotify track based on various criteria.

    Args:
        tidal_track (dict): Tidal track information.
        spotify_track (dict): Spotify track information.

    Returns:
        bool: True if the tracks match based on criteria, False otherwise.
    """
    s = {
        'artists': format_artists(spotify_track.get('artists', [])),
        'album_name': spotify_track.get('album', {}).get('name', '').lower(),
        'track_name': spotify_track.get('name', '').lower(),
        'duration': int(spotify_track.get('duration_ms', 0) / 1000),
        'isrc': spotify_track.get('external_ids', {}).get('isrc')
    }
    t = {
        'artists': format_artists(tidal_track.get('artists', [])),
        'album_name': tidal_track.get('album', {}).get('title', '').lower(),
        'track_name': tidal_track.get('title', '').lower(),
        'duration': tidal_track.get('duration', 0),
        'isrc': tidal_track.get('isrc')
    }

    criteria = 0
    criteria += all(artist in t['artists'] for artist in s['artists'])
    criteria += similar(s['album_name'], t['album_name'])
    criteria += similar(s['track_name'], t['track_name'])
    criteria += close(s['duration'], t['duration'])
    criteria += (s['isrc'] == t['isrc'])

    return criteria >= 4


def search_for_track_in_album(tidal: API, spotify_track: dict) -> list:
    """
    Search for a track within an album on Tidal based on a Spotify track.

    Args:
        tidal (API): Tidal API client.
        spotify_track (dict): Spotify track information.

    Returns:
        list: List of matching Tidal tracks.
    """
    matches = []
    s_album = spotify_track.get('album', {})
    s_album_artists = s_album.get('artists', [])
    s_artists = spotify_track.get('artists', [])
    s_num_tracks = s_album.get('total_tracks', 0)
    s_release_date = parse_date(s_album.get('release_date', ''))
    s_album_name = s_album.get('name', '')

    if not (s_album and s_album_artists and s_artists):
        return matches

    query = f"{format_string(s_album_name)} {format_string(s_album_artists[0].get('name', ''))}"
    res = tidal.search(query, country_code="CH", type='ALBUMS')

    for t_album in res.get('albums', []):
        t_album = t_album.get('resource', {})
        t_num_tracks = t_album.get('numberOfTracks', 0)
        t_release_date = parse_date(t_album.get('releaseDate', ''))
        t_album_name = t_album.get('title', '')

        if close(t_num_tracks, s_num_tracks) and (
                abs((t_release_date - s_release_date).days) < 2 or similar(t_album_name, s_album_name, 0.85)):
            time.sleep(random.uniform(0.3, 0.9))
            album_tracks = tidal.get_album_items(t_album.get('id'), country_code="CH", limit=50).get('data', [])
            for track in album_tracks:
                track = track.get('resource', {})
                if match_song(track, spotify_track):
                    matches.append(track)

    return matches


def search_for_track(tidal: API, spotify_track: dict) -> list:
    """
    Search for a Tidal track based on a Spotify track.

    Args:
        tidal (API): Tidal API client.
        spotify_track (dict): Spotify track information.

    Returns:
        list: List of matching Tidal tracks.
    """
    matches = []
    s_artists = spotify_track.get('artists', [])
    s_track_name = spotify_track.get('name', '')

    query = f"{format_string(s_track_name)} {format_string(s_artists[0].get('name', ''))}"
    res = tidal.search(query, country_code="CH", type='TRACKS')

    for track in res.get('tracks', []):
        track = track.get('resource', {})
        if match_song(track, spotify_track):
            matches.append(track)

    return matches


def get_best_quality_track(tracks: list) -> dict:
    """
    Get the track with the best quality from a list of tracks.

    Args:
        tracks (list): List of Tidal tracks.

    Returns:
        dict: Track with the best quality.
    """
    best_quality = 0
    best_track = None

    for track in tracks:
        quality = constants.TIDAL_QUALITY.get(track.get('mediaMetadata', {}).get('tags', [])[0], 0)
        if quality > best_quality:
            best_quality = quality
            best_track = track

    return best_track
