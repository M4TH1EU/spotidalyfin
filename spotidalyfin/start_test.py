from pathlib import Path

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
    spotify_playlist = spotify_manager.get_playlist("0ubAoSc3fASZQOcKNlVCzd", retrieve_all_tracks=True,
                                                    retrieve_all_albums_details=False)

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

            print("Downloading...")

            path = Path(cfg.get("out-dir"))
            path.mkdir(parents=True, exist_ok=True)

            raw_data = list_of_matches[0].download()

            print("Downloaded, saving...")

            metadata = list_of_matches[0].metadata()

            out_file = metadata.generate_path(base_path=path, extension="flac")
            out_file.parent.mkdir(parents=True, exist_ok=True)

            with open(out_file, "wb") as file:
                file.write(raw_data)

            print("Saved. Writing metadata...")

            metadata.write_to_file(out_file)

            print("Done.")
            print("")
