from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

import rich
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from tidalapi import Track

from spotidalyfin import cfg
from spotidalyfin.db.database import Database
from spotidalyfin.managers.tidal_manager import TidalManager
from spotidalyfin.utils.file_utils import file_to_list, parse_secrets_file
from spotidalyfin.utils.logger import log, setup_logger
from .managers.jellyfin_manager import JellyfinManager
from .managers.spotify_manager import SpotifyManager

app = typer.Typer()

download_app = typer.Typer()
app.add_typer(download_app, name="download")

jellyfin_app = typer.Typer()
app.add_typer(jellyfin_app, name="jellyfin")
jellyfin_app_sync = typer.Typer()
jellyfin_app.add_typer(jellyfin_app_sync, name="sync")


@app.callback()
def app_callback(debug: bool = cfg.get("debug"), secrets: Path = cfg.get("secrets")):
    cfg.put("debug", debug)
    cfg.put("secrets", secrets)
    cfg.get_config().update(parse_secrets_file(secrets))


@download_app.callback()
def download_callback(
        quality: Annotated[int, typer.Option(
            help="Quality of the downloaded tracks (1: LOW, 2: LOSSLESS, 3: HI_RES_LOSSLESS)")] = cfg.get('quality'),
        out_dir: Annotated[Path, typer.Option(help="Output directory for downloaded tracks")] = cfg.get("out-dir"),
        dl_dir: Annotated[Path, typer.Option(help="Temporary directory for downloaded tracks")] = cfg.get("dl-dir"),
        ignore_jellyfin: Annotated[bool, typer.Option(help="Doesn't check if song is already on Jellyfin")] = False,
        m4a2flac: Annotated[bool, typer.Option(help="Convert M4A files to FLAC")] = True
):
    cfg.put("quality", quality)
    cfg.put("out-dir", out_dir)
    cfg.put("dl-dir", dl_dir)
    cfg.put("ignore-jellyfin", ignore_jellyfin)
    cfg.put("m4a2flac", m4a2flac)


@download_app.command(name="liked", help="Download liked songs from Spotify")
def download_liked_songs():
    entrypoint("download", "liked")


@download_app.command(name="playlist", help="Download playlist from Spotify")
def download_playlist(playlist_id: Annotated[str, typer.Argument(help="Track ID / URL")]):
    entrypoint("download", "playlist", playlist_id=playlist_id)


@download_app.command(name="file", help="Download a list of playlist from a file from Spotify")
def download_from_file(file_path: Annotated[Path, typer.Argument(help="Path to file with playlist IDs")]):
    entrypoint("download", "file", file_path=file_path)


@download_app.command(name="track", help="Download a single track from Spotify")
def download_track(track_id: Annotated[str, typer.Argument(help="Track ID / URL")]):
    entrypoint("download", "track", track_id=track_id)


def entrypoint(command: str, action: str, **kwargs):
    setup_logger(cfg.get("debug"))

    log.info("[bold]Starting [green]Spo[white]tidal[blue]yfin...", extra={"markup": True})
    log.info(f"Current action : {action}\n")

    log.debug("Connecting to Spotify, Tidal and Jellyfin...")
    spotify_manager = SpotifyManager(cfg.get("spotify_client_id"), cfg.get("spotify_client_secret"))
    tidal_manager = TidalManager()
    jellyfin_manager = JellyfinManager(cfg.get("jellyfin_url"), cfg.get("jellyfin_api_key"))

    db = Database()

    # dumb call to verify user is logged to Spotify
    spotify_manager.client.current_user()

    if command == "download":
        entrypoint_download(action, spotify_manager, tidal_manager, jellyfin_manager, db, **kwargs)
    elif command == "jellyfin":
        entrypoint_jellyfin(action, spotify_manager, tidal_manager, jellyfin_manager, db, **kwargs)

    log.info("Done!")


def entrypoint_download(action: str, spotify_manager: SpotifyManager, tidal_manager: TidalManager,
                        jellyfin_manager: JellyfinManager, db: Database, **kwargs):
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
    already_on_jellyfin = 0
    for track in rich.progress.track(spotify_tracks_to_match, description="Matching tracks...", transient=True):
        # Match Spotify tracks ID with Tidal tracks ID
        if not track:
            continue
        if 'track' in track:
            track = track.get('track', None)

        track_data_for_jellyfin = tidal_manager.get_track(db.get(track['id'])) if db.get(track['id']) else track

        # Check if the track already exists on Jellyfin and if we should ignore it
        if cfg.get("ignore-jellyfin") is False:
            if jellyfin_manager.does_track_exist(track_data_for_jellyfin):
                log.debug(f"Track {track['name']} already exists in Jellyfin")
                already_on_jellyfin += 1
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
        # Save the match in the database
        db.put(track['id'], tidal_track.id)

    log.info(
        f"Matched {len(tidal_tracks_to_download)}/{len(spotify_tracks_to_match) - already_on_jellyfin} Spotify tracks with Tidal.\b")

    # --------------------------------------
    # Download Tidal tracks
    if not tidal_tracks_to_download:
        log.info("No tracks to download.")
        return

    files_before_download = len(list(cfg.get("out-dir").rglob("*/*/*")))

    with Progress(transient=True) as progress:
        progress.add_task(f"Total progress", total=len(tidal_tracks_to_download))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for track in tidal_tracks_to_download:
                futures.append(
                    executor.submit(tidal_manager.download_track, track, progress))

    files_after_download = len(list(cfg.get("out-dir").rglob("*/*/*")))

    if files_after_download - files_before_download == len(tidal_tracks_to_download) - cfg.get("already-downloaded", 0):
        log.info(f"[bold green]Downloaded {len(tidal_tracks_to_download)} tracks from Tidal.", extra={"markup": True})
    else:
        log.debug(f"Files before download: {files_before_download}")
        log.debug(f"Files after download: {files_after_download}")
        log.warning(
            f"[bold yellow]Some tracks might not have been downloaded correctly. Check the logs for more information.",
            extra={"markup": True})


def entrypoint_jellyfin(action: str, spotify_manager: SpotifyManager, tidal_manager: TidalManager,
                        jellyfin_manager: JellyfinManager, db: Database, **kwargs):
    if action == "compress":
        log.info("Compressing Jellyfin metadata...")

        if not cfg.get("y"):
            ask = typer.confirm(
                "Are you sure you want to compress the metadata? This is irreversible. Test it first and make sure you have a backup of the metadata directory.")
            if not ask:
                log.info("Aborting...")
                raise typer.Abort()

        with Progress(transient=True) as progress:
            jellyfin_manager.compress_metadata_images(progress)

    elif action == "sync":
        if kwargs["source"] == "liked":
            tracks = spotify_manager.get_liked_songs()
            jellyfin_manager.sync_playlist(playlist_with_tracks=tracks, user=kwargs.get("playlist_user"),
                                           tidal_manager=tidal_manager, database=db)
        elif kwargs["source"] == "playlist":
            playlist_with_tracks = spotify_manager.get_playlist_with_tracks(kwargs["playlist_id"])
            jellyfin_manager.sync_playlist(playlist_with_tracks, user=kwargs.get("playlist_user"),
                                           tidal_manager=tidal_manager, database=db)
        elif kwargs["source"] == "file":
            playlists = file_to_list(kwargs["file_path"])
            for playlist in playlists:
                playlist_with_tracks = spotify_manager.get_playlist_with_tracks(playlist)
                jellyfin_manager.sync_playlist(playlist_with_tracks, user=kwargs.get("playlist_user"),
                                               tidal_manager=tidal_manager, database=db)
        else:
            raise typer.BadParameter("Invalid source")

    elif action == "artists":
        pass


@jellyfin_app.command(name="compress",
                      help="Compresses metadata (images) of entire Jellyfin library without much quality loss")
def compress(metadata_dir: Annotated[Path, typer.Option(help="Path to Jellyfin metadata directory")] = cfg.get(
    "jellyfin-metadata-dir"), y: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False):
    cfg.put("jellyfin-metadata-dir", metadata_dir)
    cfg.put("y", y)
    entrypoint("jellyfin", "compress", metadata_dir=metadata_dir)


@jellyfin_app_sync.command(name="liked", help="Sync liked songs from Spotify to Jellyfin")
def sync_liked(user: Annotated[str, typer.Argument(help="Jellyfin user to sync the playlist to")]):
    entrypoint("jellyfin", "sync", source="liked", playlist_user=user)


@jellyfin_app_sync.command(name="playlist", help="Sync playlist from Spotify to Jellyfin")
def sync_playlist(playlist_id: Annotated[str, typer.Argument(help="Playlist ID")],
                  user: Annotated[str, typer.Argument(help="Jellyfin user to sync the playlist to")]):
    entrypoint("jellyfin", "sync", source="playlist", playlist_id=playlist_id, playlist_user=user)


@jellyfin_app_sync.command(name="file", help="Sync a list of playlists from Spotify from a file to Jellyfin")
def sync_from_file(file_path: Annotated[Path, typer.Argument(help="Path to file with playlist IDs")],
                   user: Annotated[str, typer.Argument(help="Jellyfin user to sync the playlist to")]):
    entrypoint("jellyfin", "sync", source="file", file_path=file_path, playlist_user=user)


@jellyfin_app.command(name="artists", help="Downloads artists images from Tidal and uploads them to Jellyfin")
def download_artists_images():
    pass


if __name__ == '__main__':
    app()
