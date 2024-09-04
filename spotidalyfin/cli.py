import sys
from pathlib import Path
from typing import Annotated

import rich
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from spotidalyfin.utils.file_utils import file_to_list, parse_secrets_file, get_all_files_in_directory, \
    organize_audio_file
from spotidalyfin.utils.logger import log, setup_logger
from .db.database import Database
from .managers.jellyfin_manager import JellyfinManager
from .managers.spotify_manager import SpotifyManager
from .managers.tidal_manager import TidalManager, download_tracks, get_track_quality

APPLICATION_PATH = Path(sys._MEIPASS).resolve() if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS') else Path(
    __file__).resolve().parent

app = typer.Typer()
config = {
    "debug": False,
    "out_dir": Path("~/Music/spotidalyfin").expanduser(),
    "dl_dir": Path("/tmp/spotidalyfin"),
    "secrets": APPLICATION_PATH / "spotidalyfin.secrets",
    "streamrip": APPLICATION_PATH / "streamrip",
    "quality": 3,
}

download_app = typer.Typer()
app.add_typer(download_app, name="download")

download_liked_app = typer.Typer()
download_playlist_app = typer.Typer()
download_file_app = typer.Typer()
download_track_app = typer.Typer()


@app.callback()
def main(debug: bool = config["debug"], quality: int = config['quality'], out_dir: Path = config["out_dir"],
         dl_dir: Path = config["dl_dir"],
         secrets: Path = config["secrets"]):
    global config
    config["debug"] = debug
    config["quality"] = quality
    config["out_dir"] = out_dir
    config["dl_dir"] = dl_dir
    config["secrets"] = secrets
    config["db_path"] = config["out_dir"] / ".spotidalyfin.db"
    config = config | parse_secrets_file(secrets)


@download_app.command(name="liked")
def download_liked_songs():
    entrypoint("download", "liked")


@download_app.command(name="playlist")
def download_playlist(playlist_id: Annotated[str, typer.Argument(help="Track ID / URL")]):
    entrypoint("download", "playlist", playlist_id=playlist_id)


@download_app.command(name="file")
def download_from_file(file_path: Annotated[Path, typer.Argument(help="Path to file with playlist IDs")]):
    entrypoint("download", "file", file_path=file_path)


@download_app.command(name="track")
def download_track(track_id: Annotated[str, typer.Argument(help="Track ID / URL")]):
    entrypoint("download", "track", track_id=track_id)


def entrypoint(command: str, action: str, **kwargs):
    database = Database(config.get("db_path"))
    setup_logger(config.get("debug"))

    log.info("[bold]Starting [green]Spo[white]tidal[blue]yfin...", extra={"markup": True})
    log.info(f"Current action : {command} {action} {kwargs}\n")

    log.debug("Connecting to Spotify, Tidal and Jellyfin...")
    spotify_manager = SpotifyManager(config.get("spotify_client_id"), config.get("spotify_client_secret"))
    tidal_manager = TidalManager(
        config.get("tidal_client_id"),
        config.get("tidal_client_secret"),
        database,
        config.get("tidal_country_code")
    )
    jellyfin_manager = JellyfinManager(config.get("jellyfin_url"), config.get("jellyfin_api_key"))

    if command == "download":
        spotify_tracks_to_match = []
        tidal_tracks_to_download = []

        # -------------------------------------------
        # Retrieve Spotify tracks to match with Tidal
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      transient=True) as progress:
            log.debug("Collecting Spotify tracks metadata...")
            progress.add_task("Collecting Spotify tracks metadata...")

            # Collect Spotify tracks to match with Tidal for download
            if action == "liked":
                spotify_tracks_to_match.extend(spotify_manager.get_liked_songs())
            elif action == "playlist":
                spotify_tracks_to_match.extend(spotify_manager.get_playlist_tracks(kwargs["playlist_id"]))
            elif action == "file":
                urls = file_to_list(kwargs["file_path"])
                for url in urls:
                    if "playlist" in url:
                        spotify_tracks_to_match.extend(spotify_manager.get_playlist_tracks(url))
                    else:
                        spotify_tracks_to_match.append(spotify_manager.get_track(url))
            elif action == "track":
                spotify_tracks_to_match.append(spotify_manager.get_track(kwargs["track_id"]))
        log.info(f"Found {len(spotify_tracks_to_match)} Spotify tracks.\n")

        # --------------------------------------
        # Match Spotify tracks with Tidal tracks
        log.debug("Matching Spotify tracks with Tidal...")
        for track in rich.progress.track(spotify_tracks_to_match, description="Matching tracks...", transient=True):
            # Match Spotify tracks ID with Tidal tracks ID
            if 'track' in track:
                track = track.get('track', None)
            if not track:
                continue

            if jellyfin_manager.does_track_exist(track):
                log.debug(f"Track {track['name']} already exists in Jellyfin")
                continue

            # Check if the track has already been matched and saved in the database
            database_res = database.get(track['id'])
            if database_res:
                log.debug(f"Track {track['name']} already matched with Tidal track : {database_res}")
                tidal_tracks_to_download.append(database_res)
                continue

            # Add album barcodes and some other metadata to the track
            track['album'] = spotify_manager.get_album(track['album']['id'])

            # Search for the track on Tidal
            tidal_id = tidal_manager.search_spotify_track(track)
            if not tidal_id:
                log.warning(f"Could not find track {track['name']} on Tidal")
                continue

            tidal_track = tidal_manager.get_track(tidal_id)
            log.info("[bold]Found a match:", extra={"markup": True})
            log.info("[green]Spotify: {} - {} - {}".format(track['name'], track['artists'][0]['name'],
                                                           track['album']['name']), extra={"markup": True})
            log.info("[blue] Tidal : {} - {}  - {} ({})".format(tidal_track['title'], tidal_track['artists'][0]['name'],
                                                                tidal_track['album']['title'],
                                                                get_track_quality(tidal_track, return_as_str=True)),
                     extra={"markup": True})

            # Save the match in the database
            database.put(track['id'], tidal_id)
            # Add the Tidal track to the list of tracks to download
            tidal_tracks_to_download.append(tidal_id)

        log.info(f"Matched {len(tidal_tracks_to_download)}/{len(spotify_tracks_to_match)} Spotify tracks with Tidal.\b")

        # -------------------------------------------------------
        # Display spinner until finding a way to get progress bar
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      transient=True) as progress:
            log.debug(f"Downloading {len(tidal_tracks_to_download)} from Tidal using Streamrip...")
            progress.add_task("Downloading from Tidal (this may take a while!). Check your DL_DIR for progress.")

            download_tracks(tracks=tidal_tracks_to_download, streamrip_path=config.get('streamrip'),
                            download_path=config.get("dl_dir"), quality=config.get("quality"))

        # -------------------------
        # Organize downloaded files
        log.debug("Organizing downloaded audio files...")
        for file in rich.progress.track(get_all_files_in_directory(config.get('dl_dir')), description="Organizing...",
                                        transient=True):
            organize_audio_file(file, config.get("out_dir"))

        log.info(f"Organized {len(tidal_tracks_to_download)} audio files.")
        log.info("Done!")


if __name__ == '__main__':
    app()
