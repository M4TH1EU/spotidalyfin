from difflib import SequenceMatcher

from future.backports.datetime import datetime
from minim.tidal import API

from spotidalyfin import constants


def format_string(string):
    return string.split('-')[0].strip().split('(')[0].strip().split('[')[0].strip()


def format_artists(artists: list) -> list:
    tmp = []
    for artist in artists:
        separators = ['&', 'and', ',']
        for sep in separators:
            if sep in artist:
                artist = artist.split(sep)
                break
        if isinstance(artist, list):
            tmp.extend(a.strip().lower() for a in artist)
        else:
            tmp.append(artist.get('name').lower())
    return tmp


def similar(a, b, ratio=0.9) -> float:
    return SequenceMatcher(None, a, b).ratio() > ratio


def close(a, b, delta=2) -> bool:
    return abs(a - b) < delta


def parse_date(date_str):
    if len(date_str) == 4:
        return datetime.strptime(date_str, '%Y')
    if len(date_str) == 7:
        return datetime.strptime(date_str, '%Y-%m')
    if len(date_str) == 10:
        return datetime.strptime(date_str, '%Y-%m-%d')

    return None


def match_song(tidal_track: dict, spotify_track: dict):
    s = {
        'artists': format_artists(spotify_track.get('artists')),
        'album_name': spotify_track.get('album').get('name'),
        'track_name': spotify_track.get('name'),
        'duration': int(spotify_track.get('duration_ms') / 1000),
        'isrc': spotify_track.get('external_ids').get('isrc')
    }
    t = {
        'artists': format_artists(tidal_track.get('artists')),
        'album_name': tidal_track.get('album').get('title'),
        'track_name': tidal_track.get('title'),
        'duration': tidal_track.get('duration'),
        'isrc': tidal_track.get('isrc')
    }

    s = {k: v.lower() if isinstance(v, str) else v for k, v in s.items()}
    t = {k: v.lower() if isinstance(v, str) else v for k, v in t.items()}

    criteria = 0

    if all(artist in t['artists'] for artist in s['artists']):
        criteria += 1
    if similar(s['album_name'], t['album_name']):
        criteria += 1
    if similar(s['track_name'], t['track_name']):
        criteria += 1
    if close(s['duration'], t['duration']):
        criteria += 1
    if s['isrc'] == t['isrc']:
        criteria += 1

    if criteria >= 4:
        return True

    return False


def search_for_track_in_album(tidal: API, spotify_track: dict):
    matches = []

    s_album = spotify_track.get('album')
    s_album_artists = s_album.get('artists')
    s_artists = spotify_track.get('artists')
    s_num_tracks = s_album.get('total_tracks')
    s_release_date = parse_date(s_album.get('release_date'))
    s_album_name = s_album.get('name')

    if s_album and s_album_artists and s_artists:
        query = format_string(s_album.get('name')) + " " + format_string(s_album_artists[0].get('name'))
        res = tidal.search(query, country_code="CH", type='ALBUMS')
        for t_album in res['albums']:
            t_album = t_album.get('resource')
            t_num_tracks = t_album.get('numberOfTracks')
            t_release_date = parse_date(t_album.get('releaseDate'))
            t_album_name = t_album.get('title')

            if abs(t_num_tracks - s_num_tracks) < 2:
                if abs(t_release_date - s_release_date).days < 2 or SequenceMatcher(None, t_album_name,
                                                                                    s_album_name).ratio() > 0.85:
                    res = tidal.get_album_items(t_album.get('id'), country_code="CH", limit=50)
                    for track in res['data']:
                        track = track.get('resource')
                        if match_song(track, spotify_track):
                            matches.append(track)

    return matches


def search_for_track(tidal: API, spotify_track: dict):
    matches = []

    s_artists = spotify_track.get('artists')
    s_track_name = spotify_track.get('name')

    query = format_string(s_track_name) + " " + format_string(s_artists[0].get('name'))
    res = tidal.search(query, country_code="CH", type='TRACKS')

    for track in res['tracks']:
        track = track.get('resource')

        if match_song(track, spotify_track):
            matches.append(track)

    return matches


def get_best_quality_track(tracks: list):
    best_quality = 0
    best_track = None

    for track in tracks:
        quality = constants.TIDAL_QUALITY.get(track.get('mediaMetadata').get('tags')[0], 0)
        if quality > best_quality:
            best_quality = quality
            best_track = track

    return best_track
