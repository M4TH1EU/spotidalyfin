from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, List

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
helpers_app = typer.Typer()
app.add_typer(helpers_app, name="helpers")


@app.callback()
def app_callback(debug: bool = cfg.get("debug"), secrets: Path = cfg.get("secrets")):
    """Callback for app configuration."""
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
    """Callback for download settings."""
    cfg.put("quality", quality)
    cfg.put("out-dir", out_dir)
    cfg.put("dl-dir", dl_dir)
    cfg.put("ignore-jellyfin", ignore_jellyfin)
    cfg.put("m4a2flac", m4a2flac)


# Commands for downloading
@download_app.command(name="liked", help="Download liked songs from Spotify")
def download_liked_songs():
    entrypoint("download", "liked")


@download_app.command(name="playlist", help="Download playlist from Spotify")
def download_playlist(playlist_id: Annotated[str, typer.Argument(help="Track ID / URL")]):
    entrypoint("download", "playlist", playlist_id=playlist_id)


@download_app.command(name="file", help="Download a list of playlist from a file from Spotify")
def download_from_file(file_path: Annotated[Path, typer.Argument(help="Path to file with playlist IDs")]):
    entrypoint("download", "file", file_path=Path(file_path))


@download_app.command(name="track", help="Download a single track from Spotify")
def download_track(track_id: Annotated[str, typer.Argument(help="Track ID / URL")]):
    entrypoint("download", "track", track_id=track_id)


def entrypoint(command: str, action: str, **kwargs):
    """Main entry point for commands."""
    setup_logger(cfg.get("debug"))
    log.info("[bold]Starting [green]Spo[white]tidal[blue]yfin...", extra={"markup": True})
    log.info(f"Current action: {action}\n")

    spotify_manager = SpotifyManager(cfg.get("spotify_client_id"), cfg.get("spotify_client_secret"))
    tidal_manager = TidalManager()
    jellyfin_manager = JellyfinManager(cfg.get("jellyfin_url"), cfg.get("jellyfin_api_key"))
    db = Database()

    # Ensure Spotify is connected
    spotify_manager.client.current_user()

    if command == "download":
        handle_download(action, spotify_manager, tidal_manager, jellyfin_manager, db, **kwargs)
    elif command == "jellyfin":
        handle_jellyfin(action, spotify_manager, tidal_manager, jellyfin_manager, db, **kwargs)
    elif command == "helpers":
        handle_helpers(action, spotify_manager, tidal_manager, jellyfin_manager, db, **kwargs)

    log.info("Done!")


def handle_download(action: str, spotify_manager: SpotifyManager, tidal_manager: TidalManager,
                    jellyfin_manager: JellyfinManager, db: Database, **kwargs):
    """Handles the download process based on the action."""
    spotify_tracks = get_spotify_tracks(action, spotify_manager, **kwargs)
    tidal_tracks = match_spotify_with_tidal(spotify_tracks, tidal_manager, spotify_manager, jellyfin_manager, db)
    download_tidal_tracks(tidal_tracks, tidal_manager)


def get_spotify_tracks(action: str, spotify_manager: SpotifyManager, **kwargs) -> List[dict]:
    """Retrieve Spotify tracks based on the action."""
    log.debug("Collecting Spotify tracks metadata...")
    spotify_tracks = []

    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
    ) as progress:
        progress.add_task(description="Collecting Spotify tracks metadata...", total=None)

        if action == "liked":
            spotify_tracks = spotify_manager.get_liked_songs()
        elif action == "playlist":
            spotify_tracks = spotify_manager.get_playlist_tracks(kwargs["playlist_id"])
        elif action == "file":
            urls = file_to_list(kwargs["file_path"])
            for url in urls:
                spotify_tracks.extend(spotify_manager.get_playlist_tracks(url))
        elif action == "track":
            spotify_tracks.append(spotify_manager.get_track(kwargs["track_id"]))

    log.info(f"Found {len(spotify_tracks)} Spotify tracks.\n")
    return spotify_tracks


def match_spotify_with_tidal(spotify_tracks: List[dict], tidal_manager: TidalManager, spotify_manager: SpotifyManager,
                             jellyfin_manager: JellyfinManager, db: Database) -> List[Track]:
    """Match Spotify tracks with Tidal tracks."""
    tidal_tracks_to_download = []
    already_on_jellyfin = 0

    log.debug("Matching Spotify tracks with Tidal...")
    for track in rich.progress.track(spotify_tracks, description="Matching tracks...", transient=True):
        if not track:
            continue

        if 'track' in track:
            track = track['track']

        track_from_db = db.get_tidal_track_from_database(track['id'], tidal_manager)
        if cfg.get("ignore-jellyfin") is False and jellyfin_manager.does_track_exist(track_from_db or track):
            log.debug(f"Track {track['name']} already exists in Jellyfin")
            already_on_jellyfin += 1
            continue

        # Add metadata and find track on Tidal
        track['album'] = spotify_manager.get_album(track['album']['id'])
        tidal_track = tidal_manager.search_spotify_track(track, cfg.get('quality'))

        if tidal_track:
            log_track_match(track, tidal_track)
            tidal_tracks_to_download.append(tidal_track)
            db.put(track['id'], tidal_track.id)
        else:
            log.warning(
                f"Could not find a match for {track['name']} - {track['artists'][0]['name']} - {track['album']['name']}")
            continue

    log.info(
        f"Matched {len(tidal_tracks_to_download)}/{len(spotify_tracks) - already_on_jellyfin} Spotify tracks with Tidal.")
    return tidal_tracks_to_download


def log_track_match(spotify_track: dict, tidal_track: Track):
    """Logs track matching information."""
    log.info("[bold]Found a match:", extra={"markup": True})
    log.info(
        f"[green]Spotify: {spotify_track['name']} - {spotify_track['artists'][0]['name']} - {spotify_track['album']['name']}",
        extra={"markup": True})
    log.info(
        f"[blue]Tidal: {tidal_track.full_name} - {tidal_track.artist.name} - {tidal_track.album.name} ({tidal_track.real_quality} - {tidal_track.id})\n",
        extra={"markup": True})


def download_tidal_tracks(tidal_tracks: List[Track], tidal_manager: TidalManager):
    """Download matched Tidal tracks."""
    if not tidal_tracks:
        log.info("No tracks to download.")
        return

    files_before_download = len(list(cfg.get("out-dir").rglob("*/*/*")))

    with Progress(transient=True) as progress:
        progress.add_task(f"Total progress", total=len(tidal_tracks))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(tidal_manager.download_track, track, progress) for track in tidal_tracks]

    files_after_download = len(list(cfg.get("out-dir").rglob("*/*/*")))

    if files_after_download - files_before_download == len(tidal_tracks) - cfg.get("already-downloaded", 0):
        log.info(f"[bold green]Downloaded {len(tidal_tracks)} tracks from Tidal.", extra={"markup": True})
    else:
        log.warning(
            f"[bold yellow]Some tracks might not have been downloaded correctly. Check the logs for more information.",
            extra={"markup": True})


def handle_jellyfin(action: str, spotify_manager: SpotifyManager, tidal_manager: TidalManager,
                    jellyfin_manager: JellyfinManager, db: Database, **kwargs):
    """Handles Jellyfin-related commands."""
    if action == "compress":
        compress_jellyfin_metadata(jellyfin_manager)
    elif action == "sync":
        sync_jellyfin_playlist(spotify_manager, jellyfin_manager, tidal_manager, db, **kwargs)
    elif action == "artists":
        jellyfin_manager.download_artists_images(tidal_manager, spotify_manager)


def compress_jellyfin_metadata(jellyfin_manager: JellyfinManager):
    """Compresses Jellyfin metadata."""
    log.info("Compressing Jellyfin metadata...")
    if not cfg.get("y"):
        confirm = typer.confirm("Are you sure you want to compress the metadata? This is irreversible.")
        if not confirm:
            log.info("Aborting...")
            raise typer.Abort()

    with Progress(transient=True) as progress:
        jellyfin_manager.compress_metadata_images(progress)


def sync_jellyfin_playlist(spotify_manager: SpotifyManager, jellyfin_manager: JellyfinManager,
                           tidal_manager: TidalManager, db: Database, **kwargs):
    """Syncs Spotify playlists with Jellyfin."""
    source = kwargs["source"]
    if source == "liked":
        tracks = spotify_manager.get_liked_songs()
    elif source == "playlist":
        tracks = spotify_manager.get_playlist_with_tracks(kwargs["playlist_id"])
    elif source == "file":
        playlist_ids = file_to_list(kwargs["file_path"])
        for playlist_id in playlist_ids:
            tracks = spotify_manager.get_playlist_with_tracks(playlist_id)
            jellyfin_manager.sync_playlist(playlist_with_tracks=tracks, user=kwargs.get("playlist_user"),
                                           tidal_manager=tidal_manager, database=db)

    jellyfin_manager.sync_playlist(playlist_with_tracks=tracks, user=kwargs.get("playlist_user"),
                                   tidal_manager=tidal_manager, database=db)


def handle_helpers(action: str, spotify_manager: SpotifyManager, tidal_manager: TidalManager,
                   jellyfin_manager: JellyfinManager, db: Database, **kwargs):
    """Handles helper commands."""
    if action == "playlists":
        playlists_from_user = spotify_manager.get_user_playlists(kwargs["user"])
        for playlist in playlists_from_user:
            log.info(f"{playlist['id']} - {playlist['name']} - ({playlist['owner']['display_name']})")


# Jellyfin app commands
@jellyfin_app.command(name="compress",
                      help="Compresses metadata (images) of entire Jellyfin library without much quality loss")
def compress(metadata_dir: Annotated[Path, typer.Option(help="Path to Jellyfin metadata directory")] = cfg.get(
    "jellyfin-metadata-dir"),
        y: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False):
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
    entrypoint("jellyfin", "artists")


@helpers_app.command(name="playlists", help="Print all playlists from a Spotify user")
def print_playlists(user: Annotated[str, typer.Argument(help="Spotify user ID")]):
    entrypoint("helpers", "playlists", user=user)


if __name__ == '__main__':
    app()
