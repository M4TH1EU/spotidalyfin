import datetime
import hashlib
import random
import string
from typing import List, Optional, Tuple

import requests

from spotidalyfin.models.album import SubsonicAlbum
from spotidalyfin.models.artist import SubsonicArtist
from spotidalyfin.models.enums import Platform, TrackQuality
from spotidalyfin.models.manager import Manager
from spotidalyfin.models.playlist import Playlist, SubsonicPlaylist, \
    SubsonicFavoriteTracksPlaylist
from spotidalyfin.models.track import SubsonicTrack


def _parse_artist(subsonic_artist: dict) -> SubsonicArtist:
    return SubsonicArtist(
        id=subsonic_artist.get("artistId") or subsonic_artist.get("id"),
        name=subsonic_artist.get("artist") or subsonic_artist.get("name", "Unknown Artist")
    )


def _parse_album(subsonic_album: dict, artist: Optional[SubsonicArtist] = None) -> SubsonicAlbum:
    return SubsonicAlbum(
        id=subsonic_album.get("albumId") or subsonic_album.get("id"),
        name=subsonic_album.get("album") or subsonic_album.get("name", "Unknown Album"),
        artist=artist if artist else _parse_artist(subsonic_album),
        cover_url=subsonic_album.get("coverArt"),
        barcode="",
        release_date=datetime.datetime(
            subsonic_album.get('originalReleaseDate').get('year', '1970'),
            subsonic_album.get('originalReleaseDate').get('month', 1),
            subsonic_album.get('originalReleaseDate').get('day', 1)
        ) if subsonic_album.get("originalReleaseDate") else subsonic_album.get('year', None),
        num_volumes=None,
        tracks=[_parse_track(_track) for _track in subsonic_album.get("song", [])] if isinstance(
            subsonic_album.get("song"), list) else None
    )


def _parse_track(subsonic_song: dict, artist: Optional[SubsonicArtist] = None,
                 album: Optional[SubsonicAlbum] = None) -> SubsonicTrack:
    duration = int(subsonic_song.get("duration", 0)) * 1000  # seconds to ms

    return SubsonicTrack(
        id=subsonic_song.get("id"),
        name=subsonic_song.get("title"),
        artist=artist if artist else _parse_artist(subsonic_song),
        album=album if album else _parse_album(subsonic_song, artist),
        isrc=subsonic_song.get("isrc", [""])[0] if isinstance(subsonic_song.get("isrc"), list) and len(
            subsonic_song.get("isrc")) > 0 else None,
        duration=duration,
        quality=_parse_quality(subsonic_song)
    )


def _parse_quality(subsonic_track: dict) -> TrackQuality:
    try:
        codec = subsonic_track.get('contentType', 'audio/mpeg').split('/')[1].lower()
        bit_depth = subsonic_track.get("bitDepth", 16)
        bit_rate = subsonic_track.get("bitRate", 128)
        sample_rate = subsonic_track.get("samplingRate", 44100)

        if codec in ["mp3", "aac", "opus"]:
            return TrackQuality.LOW
        if codec == "flac":
            if (bit_depth == 16 or bit_rate >= 1000) and sample_rate >= 44100:
                return TrackQuality.LOSSLESS
            if (bit_depth == 24 or bit_rate >= 1000) and sample_rate >= 48000:  # TODO: do this correctly
                return TrackQuality.HI_RES_LOSSLESS
            return TrackQuality.LOSSLESS  # fallback for flac

    except (IndexError, AttributeError, TypeError):
        pass

    return TrackQuality.UNKNOWN


def _generate_salt(length: int = 10) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def _generate_token(password: str, salt: str) -> str:
    return hashlib.md5((password + salt).encode("utf-8")).hexdigest()


class SubsonicManager(Manager):
    PLATFORM = Platform.SUBSONIC

    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.api_version = "1.16.1"
        self.client_name = "spotidalyfin"

    def _request(self, endpoint: str, params: dict = None) -> dict:
        salt = _generate_salt()
        token = _generate_token(self.password, salt)

        default_params = {
            "u": self.username,
            "t": token,
            "s": salt,
            "v": self.api_version,
            "c": self.client_name,
            "f": "json"
        }
        all_params = {**default_params, **(params or {})}
        response = requests.get(f"{self.base_url}/rest/{endpoint}.view", params=all_params)
        response.raise_for_status()
        resp_json = response.json()

        if resp_json.get("subsonic-response", {}).get("status") == "failed":
            raise ValueError(f"Subsonic API error: {resp_json['subsonic-response'].get('error')}")

        return resp_json["subsonic-response"]

    def is_multi_user(self) -> bool:
        return True

    def get_users(self) -> List[Tuple[str, str]]:
        resp = self._request("getUsers")
        return [(u["username"], u["username"]) for u in resp.get("users", {}).get("user", [])]

    def get_track(self, track_id: str) -> Optional[SubsonicTrack]:
        resp = self._request("getSong", {"id": track_id})
        song = resp.get("song")
        if not song:
            return None
        return _parse_track(song)

    def get_album(self, album_id: str) -> Optional[SubsonicAlbum]:
        resp = self._request("getAlbum", {"id": album_id})
        album_data = resp.get("album")
        if not album_data:
            return None
        return _parse_album(album_data)

    def get_artist(self, artist_id: str) -> Optional[SubsonicArtist]:
        resp = self._request("getArtist", {"id": artist_id})
        artist_data = resp.get("artist")
        if not artist_data:
            return None
        return _parse_artist(artist_data)

    def get_artist_tracks(self, artist_id: str) -> List[SubsonicTrack]:
        resp = self._request("getArtist", {"id": artist_id})
        artist = _parse_artist(resp.get("artist"))
        albums = resp.get("artist", {}).get("album", [])
        tracks = []
        for album in albums:
            album_obj = _parse_album(album, artist)
            album_detail = self._request("getAlbum", {"id": album["id"]}).get("album")
            for song in album_detail.get("song", []):
                tracks.append(_parse_track(song, artist, album_obj))
        return tracks

    def get_playlist(self, playlist_id: str, fetch_tracks: bool = True, fetch_albums: bool = False) -> Optional[
        SubsonicPlaylist]:
        resp = self._request("getPlaylist", {"id": playlist_id})
        playlist = resp.get("playlist")
        tracks = []
        if fetch_tracks:
            for s in playlist.get("entry", []):
                tracks.append(_parse_track(s))
        return SubsonicPlaylist(id=playlist_id, name=playlist.get("name"), tracks=tracks, image=None)

    def get_user_playlists(self, user_id: str = None) -> List[SubsonicPlaylist]:
        resp = self._request("getPlaylists")
        playlists = []
        for pl in resp.get("playlists", {}).get("playlist", []):
            playlists.append(Playlist(id=pl.get("id"), name=pl.get("name"), tracks=[]))
        return playlists

    def get_favorite_tracks(self, user_id: str = None) -> Optional[SubsonicFavoriteTracksPlaylist]:
        resp = self._request("getStarred")
        songs = resp.get("starred", {}).get("song", [])
        tracks = []
        for s in songs:
            tracks.append(_parse_track(s))
        return SubsonicFavoriteTracksPlaylist(name="Starred", tracks=tracks)

    def search_tracks_by_query(self, query: str) -> List[SubsonicTrack]:
        resp = self._request("search3", {"query": query})
        songs = resp.get("searchResult3", {}).get("song", [])
        results = []
        for s in songs:
            results.append(_parse_track(s))
        return results

    def search_tracks_by_isrc(self, isrc: str) -> List[SubsonicTrack]:
        return []  # Subsonic does not support ISRC natively

    def search_albums_by_query(self, query: str) -> List[SubsonicAlbum]:
        resp = self._request("search3", {"query": query, "songCount": 0, "artistCount": 0})
        albums = []
        for a in resp.get("searchResult3", {}).get("album", []):
            albums.append(_parse_album(a))
        return albums

    def search_albums_by_upc(self, upc: str) -> List[SubsonicAlbum]:
        return []  # Subsonic does not support UPC

    def search_artists_by_query(self, query: str) -> List[SubsonicArtist]:
        resp = self._request("search3", {"query": query})
        return [_parse_artist(a) for a in resp.get("searchResult3", {}).get("artist", [])]

    def supports_lyrics(self) -> bool:
        return True

    def get_lyrics(self, track: SubsonicTrack) -> str:
        resp = self._request("getLyrics", {"artist": track.artist.name, "title": track.name})
        return resp.get("lyrics", "")

    def create_empty_playlist(self, name: str, description: str = "", cover_url: str = "", user_id: str = None) -> \
            Optional[SubsonicPlaylist]:
        resp = self._request("createPlaylist", {"name": name})
        if resp.get("status") == "ok":
            pl_id = resp.get("playlist", {}).get("id")
            return SubsonicPlaylist(id=pl_id, name=name, tracks=[])
        return None

    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[SubsonicTrack]) -> bool:
        track_ids = [t.id for t in tracks]
        self._request("updatePlaylist", {
            "playlistId": playlist.id,
            "songId": track_ids
        })
        return True

    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        self._request("deletePlaylist", {"id": playlist_id})
        return True
