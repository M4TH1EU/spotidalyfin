from spotidalyfin import cfg
from spotidalyfin.managers.spotify_manager import SpotifyManager
from spotidalyfin.managers.tidal_manager import TidalManager
from spotidalyfin.utils.file_utils import parse_secrets_file

if __name__ == '__main__':
    cfg.get_config().update(parse_secrets_file(cfg.get("secrets").parent.parent / "spotidalyfin.secrets"))
    spotify_manager = SpotifyManager(cfg.get("spotify_client_id"), cfg.get("spotify_client_secret"))
    cfg.get_config().update(parse_secrets_file(cfg.get("secrets").parent.parent / "spotidalyfin.secrets"))
    tidal_manager = TidalManager()

    spotify_playlist = spotify_manager.get_playlist("7pjGkZGtVdbrah9iusz4QU", retrieve_tracks=True,
                                                    retrieve_albums=True)

    for track in spotify_playlist.tracks:
        tidal_search = tidal_manager.search_tracks(track_name=track.name, artist_name=track.artist.name,
                                                   isrc=track.isrc)
        print(track.name)

        for result in tidal_search:
            print(result)
            print(track.matches(result))
