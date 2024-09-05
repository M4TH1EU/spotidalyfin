from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

import rich
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from tidalapi import Track

from spotidalyfin import cfg
from spotidalyfin.managers.tidal_manager import TidalManager
from spotidalyfin.utils.file_utils import file_to_list, parse_secrets_file
from spotidalyfin.utils.logger import log, setup_logger
from .managers.jellyfin_manager import JellyfinManager
from .managers.spotify_manager import SpotifyManager

app = typer.Typer()

download_app = typer.Typer()
app.add_typer(download_app, name="download")


@app.callback()
def main(debug: bool = cfg.get("debug"), quality: int = cfg.get('quality'), out_dir: Path = cfg.get("out-dir"),
         dl_dir: Path = cfg.get("dl-dir"),
         secrets: Path = cfg.get("secrets")):
    cfg.put("debug", debug)
    cfg.put("quality", quality)
    cfg.put("out-dir", out_dir)
    cfg.put("dl-dir", dl_dir)
    cfg.put("secrets", secrets)
    # cfg.put("db_path", cfg.get("dl-dir") / ".spotidalyfin.db")
    cfg.get_config().update(parse_secrets_file(secrets))


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
    # database = Database(config.get("db_path"))
    setup_logger(cfg.get("debug"))

    log.info("[bold]Starting [green]Spo[white]tidal[blue]yfin...", extra={"markup": True})
    log.info(f"Current action : {command} {action} {kwargs}\n")

    log.debug("Connecting to Spotify, Tidal and Jellyfin...")
    spotify_manager = SpotifyManager(cfg.get("spotify_client_id"), cfg.get("spotify_client_secret"))
    tidal_manager = TidalManager()
    jellyfin_manager = JellyfinManager(cfg.get("jellyfin_url"), cfg.get("jellyfin_api_key"))

    # dumb call to verify user is logged to Spotify
    spotify_manager.client.current_user()

    if command == "download":
        spotify_tracks_to_match: list[dict] = []
        tidal_tracks_to_download: list[Track] = []

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
            if not track:
                continue
            if 'track' in track:
                track = track.get('track', None)

            if jellyfin_manager.does_track_exist(track):
                log.debug(f"Track {track['name']} already exists in Jellyfin")
                continue

            # Add album barcodes and some other metadata to the track
            track['album'] = spotify_manager.get_album(track['album']['id'])

            # Search for the track on Tidal
            tidal_track = tidal_manager.search_spotify_track(track, cfg.get('quality'))
            if not tidal_track:
                log.warning(f"Could not find track {track['name']} on Tidal")
                continue

            tidal_track.spotify_id = track['id']

            log.info("[bold]Found a match:", extra={"markup": True})
            log.info("[green]Spotify: {} - {} - {}".format(track['name'], track['artists'][0]['name'],
                                                           track['album']['name']), extra={"markup": True})
            log.info("[blue] Tidal : {} - {}  - {} ({} - {})\n".format(tidal_track.full_name, tidal_track.artist.name,
                                                                       tidal_track.album.name, tidal_track.real_quality,
                                                                       tidal_track.id),
                     extra={"markup": True})

            # Add the Tidal track to the list of tracks to download
            tidal_tracks_to_download.append(tidal_track)

        log.info(f"Matched {len(tidal_tracks_to_download)}/{len(spotify_tracks_to_match)} Spotify tracks with Tidal.\b")

        # --------------------------------------
        # Download Tidal tracks
        with Progress(transient=True) as progress:
            progress.add_task(f"Total progress", total=len(tidal_tracks_to_download))

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for track in tidal_tracks_to_download:
                    futures.append(
                        executor.submit(tidal_manager.download_track, track, progress))

        # TODO: check if everything was downloaded correctly
        log.info(f"[bold green]Downloaded {len(tidal_tracks_to_download)} tracks from Tidal.", extra={"markup": True})
        log.info("Done!")


if __name__ == '__main__':
    app()
