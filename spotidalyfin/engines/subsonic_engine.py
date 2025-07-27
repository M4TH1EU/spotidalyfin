import hashlib
import random
import string

import requests
from spotidalyfin.models import Track, Album, Artist
from spotidalyfin.models.artist import SubsonicArtist
from spotidalyfin.models.manager import Manager
from spotidalyfin.models.playlist import Playlist, FavoriteTracksPlaylist
from spotidalyfin.models.enums import Platform, TrackQuality
from typing import List, Optional, Tuple

def _parse_artist(subsonic_artist: dict) -> Artist:
    return SubsonicArtist(
        id=subsonic_artist.get("artistId") or subsonic_artist.get("id"),
        name=subsonic_artist.get("artist") or subsonic_artist.get("name", "Unknown Artist")
    )


def _parse_album(subsonic_album: dict, artist: Artist) -> Album:
    return Album(
        id=subsonic_album.get("albumId"),
        name=subsonic_album.get("album"),
        artist=artist,
        cover_url="",
        barcode="",
        release_date=None,  # Subsonic doesn't always provide this
        num_volumes=None,
        tracks=None,
    )

def _parse_track(subsonic_song: dict, artist: Artist, album: Album) -> Track:
    duration = int(subsonic_song.get("duration", 0)) * 1000  # seconds to ms

    return Track(
        id=subsonic_song.get("id"),
        name=subsonic_song.get("title"),
        artist=artist,
        album=album,
        isrc=None,
        duration=duration,
        quality=TrackQuality.LOW if subsonic_song.get("bitRate", 128) <= 192 else TrackQuality.LOSSLESS,
    )

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

    def get_track(self, track_id: str) -> Optional[Track]:
        resp = self._request("getSong", {"id": track_id})
        song = resp.get("song")
        if not song:
            return None
        artist = Artist(id=song.get("artistId"), name=song.get("artist"))
        album = Album(id=song.get("albumId"), name=song.get("album"), artist=artist)
        return _parse_track(song, artist, album)

    def get_album(self, album_id: str) -> Optional[Album]:
        resp = self._request("getAlbum", {"id": album_id})
        album_data = resp.get("album")
        if not album_data:
            return None
        artist = Artist(id=album_data.get("artistId"), name=album_data.get("artist"))
        return _parse_album(album_data, artist)

    def get_artist(self, artist_id: str) -> Optional[Artist]:
        resp = self._request("getArtist", {"id": artist_id})
        artist_data = resp.get("artist")
        if not artist_data:
            return None
        return _parse_artist(artist_data)

    def get_artist_tracks(self, artist_id: str) -> List[Track]:
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

    def get_playlist(self, playlist_id: str, fetch_tracks: bool = True, fetch_albums: bool = False) -> Optional[Playlist]:
        resp = self._request("getPlaylist", {"id": playlist_id})
        playlist = resp.get("playlist")
        tracks = []
        if fetch_tracks:
            for s in playlist.get("entry", []):
                artist = Artist(id=s.get("artistId"), name=s.get("artist"))
                album = Album(id=s.get("albumId"), name=s.get("album"), artist=artist)
                tracks.append(_parse_track(s, artist, album))
        return Playlist(id=playlist_id, name=playlist.get("name"), tracks=tracks, image=None)

    def get_user_playlists(self, user_id: str = None) -> List[Playlist]:
        resp = self._request("getPlaylists")
        playlists = []
        for pl in resp.get("playlists", {}).get("playlist", []):
            playlists.append(Playlist(id=pl.get("id"), name=pl.get("name"), tracks=[]))
        return playlists

    def get_favorite_tracks(self, user_id: str = None) -> Optional[FavoriteTracksPlaylist]:
        resp = self._request("getStarred")
        songs = resp.get("starred", {}).get("song", [])
        tracks = []
        for s in songs:
            artist = Artist(id=s.get("artistId"), name=s.get("artist"))
            album = Album(id=s.get("albumId"), name=s.get("album"), artist=artist)
            tracks.append(_parse_track(s, artist, album))
        return FavoriteTracksPlaylist(name="Starred", tracks=tracks)

    def search_tracks_by_query(self, query: str) -> List[Track]:
        resp = self._request("search3", {"query": query})
        songs = resp.get("searchResult3", {}).get("song", [])
        results = []
        for s in songs:
            artist = _parse_artist(s)
            album = _parse_album(s, artist)
            results.append(_parse_track(s, artist, album))
        return results

    def search_tracks_by_isrc(self, isrc: str) -> List[Track]:
        return []  # Subsonic does not support ISRC natively

    def search_albums_by_query(self, query: str) -> List[Album]:
        resp = self._request("search3", {"query": query})
        albums = []
        for a in resp.get("searchResult3", {}).get("album", []):
            artist = Artist(id=a.get("artistId"), name=a.get("artist"))
            albums.append(_parse_album(a, artist))
        return albums

    def search_albums_by_upc(self, upc: str) -> List[Album]:
        return []  # Subsonic does not support UPC

    def search_artists_by_query(self, query: str) -> List[Artist]:
        resp = self._request("search3", {"query": query})
        return [_parse_artist(a) for a in resp.get("searchResult3", {}).get("artist", [])]

    def supports_lyrics(self) -> bool:
        return True

    def get_lyrics(self, track: Track) -> str:
        resp = self._request("getLyrics", {"artist": track.artist.name, "title": track.name})
        return resp.get("lyrics", "")

    def create_empty_playlist(self, name: str, description: str = "", cover_url: str = "", user_id: str = None) -> \
    Optional[Playlist]:
        resp = self._request("createPlaylist", {"name": name})
        if resp.get("status") == "ok":
            pl_id = resp.get("playlist", {}).get("id")
            return Playlist(id=pl_id, name=name, tracks=[])
        return None

    def add_tracks_to_playlist(self, playlist: Playlist, tracks: List[Track]) -> bool:
        track_ids = [t.id for t in tracks]
        self._request("updatePlaylist", {
            "playlistId": playlist.id,
            "songId": track_ids
        })
        return True

    def remove_playlist_by_id(self, playlist_id: str) -> bool:
        self._request("deletePlaylist", {"id": playlist_id})
        return True
