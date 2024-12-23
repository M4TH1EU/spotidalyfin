import datetime
import unittest

from spotidalyfin import cfg
from spotidalyfin.managers.spotify_manager import SpotifyManager
from spotidalyfin.managers.track import Album, Artist
from spotidalyfin.utils.file_utils import parse_secrets_file


class SpotifyTests(unittest.TestCase):
    def setUp(self):
        cfg.get_config().update(parse_secrets_file(cfg.get("secrets").parent.parent / "spotidalyfin.secrets"))
        self.spotify_manager = SpotifyManager(cfg.get("spotify_client_id"), cfg.get("spotify_client_secret"))
        self.track = self.spotify_manager.get_track("2BZjcbZpQyyhpVr3gMGPn6")
        self.album = self.spotify_manager.get_album("38vdzwOSCNDvh81G0QmGfk")
        self.artist = self.spotify_manager.get_artist("2bToe6WyGvADJftreuXh2K")

    def test_spotify_connection(self):
        self.assertTrue(self.spotify_manager.client.current_user() is not None)

    def test_track_name(self):
        self.assertTrue(self.track.name, "Wish You Were Here")

    def test_track_artist(self):
        expected_artist = Artist(
            name="Lee Fields & The Expressions",
            artist_id="2bToe6WyGvADJftreuXh2K"
        )
        self.assertEqual(self.track.artist, expected_artist)

    def test_track_album(self):
        expected_album = Album(
            name="Faithful Man",
            artists=[
                Artist(name="Lee Fields", artist_id="3MAzDpqE01xyUmzNsc0Ee0"),
                Artist(name="Lee Fields & The Expressions", artist_id="2bToe6WyGvADJftreuXh2K")
            ],
            release_date=datetime.datetime(2012, 3, 13),
            tracks=[None, None, None, None, None, None, None, None, None, None],
            album_id="38vdzwOSCNDvh81G0QmGfk"
        )

        self.assertEqual(self.track.album.name, expected_album.name)
        self.assertEqual(self.track.album.artists, expected_album.artists)
        self.assertEqual(self.track.album.release_date, expected_album.release_date)
        self.assertEqual(self.track.album.tracks, expected_album.tracks)
        self.assertEqual(self.track.album.album_id, expected_album.album_id)

    def test_track_duration(self):
        self.assertEqual(self.track.duration, 252)

    def test_track_artists(self):
        artists = [
            Artist(name="Lee Fields", artist_id="3MAzDpqE01xyUmzNsc0Ee0"),
            Artist(name="Lee Fields & The Expressions", artist_id="2bToe6WyGvADJftreuXh2K")
        ]

        for artist in artists:
            self.assertTrue(artist in self.track.artists)

    def test_track_isrc(self):
        self.assertEqual(self.track.isrc, "USA371618588")

    def test_album(self):
        expected_album = Album(
            name="Faithful Man",
            artists=[
                Artist(name="Lee Fields", artist_id="3MAzDpqE01xyUmzNsc0Ee0"),
                Artist(name="Lee Fields & The Expressions", artist_id="2bToe6WyGvADJftreuXh2K")
            ],
            release_date=datetime.datetime(2012, 3, 13),
            tracks=[None, None, None, None, None, None, None, None, None, None],
            album_id="38vdzwOSCNDvh81G0QmGfk"
        )

        self.assertEqual(self.album.name, expected_album.name)
        for artist in expected_album.artists:
            self.assertTrue(artist in self.album.artists)

        self.assertEqual(self.album.release_date, expected_album.release_date)
        self.assertEqual(self.album.tracks, expected_album.tracks)
        self.assertEqual(self.album.album_id, expected_album.album_id)

    def test_artist(self):
        expected_artist = Artist(
            name="Lee Fields & The Expressions",
            artist_id="2bToe6WyGvADJftreuXh2K"
        )
        self.assertEqual(self.artist.name, expected_artist.name)
        self.assertEqual(self.artist.artist_id, expected_artist.artist_id)

    def test_search_artist(self):
        artist = self.spotify_manager.search_artist("Lee Fields & The Expressions")
        expected_artist = Artist(
            name="Lee Fields & The Expressions",
            artist_id="2bToe6WyGvADJftreuXh2K"
        )
        self.assertEqual(artist, expected_artist)