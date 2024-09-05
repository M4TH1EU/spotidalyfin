![logo](.git-assets/logo.webp)
# Spotidalyfin

This project is an easy to use tool to download all your Spotify songs and playlists in **FLAC High Quality** using a
trial *(or not)* Tidal account.

> [!NOTE]
> As the name suggests, this project is meant to be a bridge between Spotify and Jellyfin.
> My use case while developing this project was to keep using Spotify as my main music streaming service, but also to have
> a local copy of my library in a higher quality to use with better audio equipment than my smartphone.

## Features

- **Download** all your Spotify songs and playlists in high quality.
- **Sync** your Spotify library locally.
- **Precise** tracks and albums matching
- **Easy** to use

## Installation

Simply download the latest release from the [releases page](./releases) and run the executable.

The following platforms are currently supported:

- **Linux** (x86_64)

## Configuration

Before running the tool you have to create a spotify app in
the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications).
When creating the app, make sure to set the following redirect URI:

```
http://127.0.0.1:6969
```

Then create a text file with the following content:

```bash
SPOTIFY_CLIENT_ID=<your_spotify_client_id>
SPOTIFY_CLIENT_SECRET=<your_spotify_client_secret>
```

Now just run the tool with the parameter `--secrets <path_to_your_secret_file>`.

> [!NOTE]
> It is also possible to build the app and bundle the secrets file in the executable. This way you don't have to worry
> about the secrets file.
> Follow the instructions in the [Development](#development) section and then run the build.sh script. You will find the
> executable in the dist folder.

## Usage

To see the available commands and options, run the following command:

```bash
$ spotidalyfin --help

 Usage: spotidalyfin-1.0.0_linux_x86_64 [OPTIONS] COMMAND [ARGS]...                                           
                                                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --debug                 --no-debug             [default: no-debug]                                         │
│ --quality                             INTEGER  [default: 3]                                                │
│ --out-dir                             PATH     [default: /home/mathieu/Music/spotidalyfin]                 │
│ --dl-dir                              PATH     [default: /tmp/spotidalyfin]                                │
│ --secrets                             PATH     [default: /tmp/_MEI3PpYzy/spotidalyfin.secrets]             │
│ --install-completion                           Install completion for the current shell.                   │
│ --show-completion                              Show completion for the current shell, to copy it or        │
│                                                customize the installation.                                 │
│ --help                                         Show this message and exit.                                 │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────────────╮
│ download                                                                                                   │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### Examples

#### Download all your Spotify liked songs
```bash
$ spotidalyfin download liked
```

#### Download a specific playlist
```bash
$ spotidalyfin download playlist <spotify_playlist_id>
```

#### Download a specific track
```bash
$ spotidalyfin download track <spotify_track_id>
```

#### Download from a list of Spotify URIs
**Note:** The URIs file should contain one URI per line.
```bash
$ spotidalyfin download file <path_to_file>
```


## Development

To modify this tool, you will need to have the following dependencies installed:

- Python 3.10+ *(tested on 3.12)*

### Build
```bash
$ python -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
$ ./build.sh
```