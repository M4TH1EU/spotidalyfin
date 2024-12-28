from spotidalyfin import cfg
from spotidalyfin.managers.spotify_manager import SpotifyManager
from spotidalyfin.managers.tidal_manager import TidalManager
from spotidalyfin.utils.file_utils import parse_secrets_file

if __name__ == '__main__':
    cfg.get_config().update(parse_secrets_file(cfg.get("secrets").parent.parent / "spotidalyfin.secrets"))
    spotify_manager = SpotifyManager(cfg.get("spotify_client_id"), cfg.get("spotify_client_secret"))
    cfg.get_config().update(parse_secrets_file(cfg.get("secrets").parent.parent / "spotidalyfin.secrets"))
    tidal_manager = TidalManager()

    print("Fetching playlist songs")
    spotify_playlist = spotify_manager.get_playlist("5eJ5L8cS2iGsbEu47YWKvK", retrieve_tracks=True,
                                                    retrieve_albums=False)

    for spotify_track in spotify_playlist.tracks:
        print(f"Searching for : {spotify_track.name} by {spotify_track.artist.name} from {spotify_track.album.name}")
        tidal_search = tidal_manager.search_tracks(track_name=spotify_track.name, artist_name=spotify_track.artist.name,
                                                   isrc=spotify_track.isrc)
        list_of_matches = []
        for tidal_track in tidal_search:
            if spotify_track.matches(other=tidal_track):
                print(
                    f"Matched : {tidal_track.name} by {tidal_track.artist.name} from {tidal_track.album.name} - {tidal_track.quality.name} - {tidal_track.score}")
                list_of_matches.append(tidal_track)
                # break
            else:
                print(
                    f"Failed to match : {tidal_track.name} by {tidal_track.artist.name} from {tidal_track.album.name} - {tidal_track.quality.name} - {tidal_track.score}")

        if not list_of_matches:
            print("No matches found")
            print("")
            continue
        else:
            list_of_matches.sort(key=lambda x: x.quality.value + x.score, reverse=True)
            print(
                f"Best match : {list_of_matches[0].name} by {list_of_matches[0].artist.name} from {list_of_matches[0].album.name} - {list_of_matches[0].quality.name} - {list_of_matches[0].score}")
            print("")

            raw_data = list_of_matches[0].download()
