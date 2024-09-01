import json
import os
import re
import sys
import time
from io import StringIO

import requests
import tidal_dl_ng.cli as tidal_dl_ng
from minim import spotify, tidal
from minim.audio import Audio

import const

DOWNLOAD_PATH = "/home/mathieu/Téléchargements/notnoice/Tracks"
FINAL_PATH = "/home/mathieu/Téléchargements/noice"

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

spotify_tidal_table = {}


class Capturing(list):
    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = self._stringio = StringIO()
        sys.stderr = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio  # free up some memory
        sys.stdout = self._stdout
        sys.stderr = self._stderr


def slugify(value):
    value = re.sub(r'[^\w_. -]', '_', value)
    return value

def get_playlist_tracks(playlist_id):
    results = client_spotify.get_playlist_items(playlist_id, limit=50)
    tracks = results['items']
    while results['next']:
        results = client_spotify.get_playlist_items(playlist_id, limit=50, offset=len(tracks))
        tracks.extend(results['items'])

    return tracks


def get_liked_songs():
    results = client_spotify.get_saved_tracks(limit=50)
    tracks = results['items']
    while results['next']:
        results = client_spotify.get_saved_tracks(limit=50, offset=len(tracks))
        tracks.extend(results['items'])
    return tracks


def search_jellyfin(track_name, artist_name, album_name):
    track_name = track_name.lower()
    artist_name = artist_name.lower()
    album_name = album_name.lower()

    request = f"{const.JELLYFIN_URL}/Items?api_key={const.JELLYFIN_API_KEY}&searchTerm={track_name}&Recursive=True&IncludeItemTypes=Audio&Limit=3"
    response = requests.get(request)
    response = response.json()

    if response['TotalRecordCount'] > 0:
        for item in response['Items']:
            if item['Type'] == "Audio":
                if track_name in item['Name'].lower():
                    if artist_name in item['Artists'][0].lower():
                        if album_name in item['Album'].lower():
                            return {
                                "id": item['Id'],
                                "name": item['Name'],
                                "artist": item['Artists'][0],
                                "album": item['Album']
                            }

    return None


def get_formatted_str(string, removes=None):
    if removes is None:
        removes = [" '", "' ", "(", ")", "[", "]", "- ", " -", "And "]

    string = string.lower()
    for remove in removes:
        string = string.replace(remove, "")
    return string


def get_tidal_track_id(track_name, artist_name, album_name, spotify_id, duration, query=None) -> list:
    try:
        if spotify_id in spotify_tidal_table:
            if not spotify_tidal_table[spotify_id]:
                return None
            return [spotify_tidal_table[spotify_id], track_name, artist_name, album_name]
        else:
            time.sleep(1.5)  # avoid 429 rate limit errors
            track_name = get_formatted_str(track_name)
            artist_name = get_formatted_str(artist_name)
            album_name = get_formatted_str(album_name)
            album_name_list = list(album_name.replace(" ", ""))

            results = client_tidal.search(f'{track_name} {artist_name}' if not query else query, "CH", type="TRACKS",
                                          limit=15)
            for track in results['tracks']:
                track = track['resource']

                tidal_track_name: str = get_formatted_str(track['title'])
                tidal_artist_name: str = get_formatted_str(track['artists'][0]['name'])
                tidal_album_name: str = get_formatted_str(track['album']['title'])
                tidal_album_name_list = list(tidal_artist_name.replace(" ", ""))
                duration_diff = abs(duration - track['duration'])

                match_criteria = 0

                if track_name in tidal_track_name:
                    match_criteria += 1
                if artist_name in tidal_artist_name:
                    match_criteria += 1

                if album_name_list == tidal_album_name_list:
                    match_criteria += 1
                elif album_name in tidal_album_name:
                    match_criteria += 1

                if duration_diff < 3:
                    match_criteria += 1

                if match_criteria >= 3:
                    write_spotify_tidal_table(spotify_id, track['id'])
                    return [track['id'], track['title'], track['artists'][0]['name'], track['album']['title']]

        retry = get_tidal_track_id(track_name, artist_name, album_name, spotify_id, duration,
                                   query=f"{artist_name} {track_name}")
        if retry:
            write_spotify_tidal_table(spotify_id, retry[0])
            return retry

        write_spotify_tidal_table(spotify_id, "")
        return []
    except RuntimeError:
        print("Tidal API error, waiting 3 seconds...")
        time.sleep(3)
        return get_tidal_track_id(track_name, artist_name, album_name, spotify_id, duration, query)


def create_spotify_tidal_table():
    if not os.path.exists(os.path.join(application_path, "spotify_tidal_table.json")):
        with open(os.path.join(application_path, "spotify_tidal_table.json"), "w+") as file:
            file.write("{}")


def read_spotify_tidal_table():
    with open(os.path.join(application_path, "spotify_tidal_table.json"), "r") as file:
        return json.load(file)


def write_spotify_tidal_table(spotify_id, tidal_id):
    with open(os.path.join(application_path, "spotify_tidal_table.json"), "w+") as file:
        spotify_tidal_table[spotify_id] = tidal_id
        json.dump(spotify_tidal_table, file)


def download_track_from_tidal(uri: str):
    sys.argv = ["tidal-dl-ng", "dl", uri]
    try:
        with Capturing() as output:
            tidal_dl_ng.app()

        if "is unavailable" in output:
            time.sleep(1)
            tidal_dl_ng.app()

            if "is unavailable" in output:
                print("  Download failed.")
                return

    except SystemExit:
        pass

    print("  Downloaded!")


def format_file_path(metadata):
    def if2(val1, val2):
        return val1 if val1 else val2

    def gt(val1, val2):
        return val1 > val2

    def num(value, digits):
        return f"{value:0{digits}d}"

    albumartist = metadata.get('albumartist', '')
    artist = metadata.get('artist', '')
    album = metadata.get('album', '')
    totaldiscs = metadata.get('totaldiscs', 1)
    discnumber = metadata.get('discnumber', 1)
    tracknumber = metadata.get('tracknumber', None)
    title = metadata.get('title', '')
    multiartist = metadata.get('_multiartist', False)

    # Equivalent logic to the given script
    result = if2(albumartist, artist) + "/"

    if albumartist:
        result += album + "/"

    if gt(totaldiscs, 1):
        result += (num(discnumber, 2) if gt(totaldiscs, 9) else str(discnumber)) + "-"

    if albumartist and tracknumber:
        result += num(tracknumber, 2) + " "

    if multiartist:
        result += artist + " - "

    result += title

    return result


def organise_track(track_name, artist_name, album_name):
    # get the only file in the download folder
    files = os.listdir(DOWNLOAD_PATH)
    if len(files) != 1:
        print("  Error: More than one file in the download folder.")

    # get the file path
    audio_data = Audio(DOWNLOAD_PATH + "/" + files[0])
    metadata = {
        "albumartist": audio_data.album_artist,
        "artist": audio_data.artist,
        "album": audio_data.album,
        "title": audio_data.title,
        "totaldiscs": audio_data.disc_count,
        "discnumber": audio_data.disc_number,
        "tracknumber": audio_data.track_number,
        "_multiartist": False,
    }
    file_path = format_file_path(metadata)  # 'Nassi/La vie est belle/01 La vie est belle'

    old_path = DOWNLOAD_PATH + "/" + files[0]
    new_path = FINAL_PATH + "/" + file_path + ".m4a"

    # move file
    os.system(f"mkdir -p '{os.path.dirname(new_path)}'")
    os.system(f"mv '{old_path}' '{new_path}'")


if __name__ == '__main__':

    tidaldlng_config = "~/.config/tidal_dl_ng/settings.json"
    my_tidaldlng_config = os.path.join(application_path, "config-tidal-dl-ng.json")
    os.system(f"cp {my_tidaldlng_config} {tidaldlng_config}")

    minim_config = "~/minim.cfg"
    my_minim_config = os.path.join(application_path, "config-minim.cfg")
    # os.system(f"cp {my_minim_config} {minim_config}")

    create_spotify_tidal_table()
    spotify_tidal_table = read_spotify_tidal_table()

    client_tidal = tidal.API(client_id=const.TIDAL_CLIENT_ID, client_secret=const.TIDAL_CLIENT_SECRET)
    scopes = spotify.WebAPI.get_scopes("all")
    client_spotify = spotify.WebAPI(client_id=const.SPOTIFY_CLIENT_ID, client_secret=const.SPOTIFY_CLIENT_SECRET,
                                    flow="pkce", scopes=scopes, web_framework="http.server")

    # liked_songs = get_liked_songs()

    spotify_playlists = client_spotify.get_user_playlists("mathieu.broillet", limit=50)
    spotify_playlists_to_save = [
        "6lTWnnpSRi7KRuaw52C44H",  # Cynthia (Cynthia Broillet)
        "0q63F2FaPTWyPiCDfPLKga",  # Old Money 💸 (Carter Beau)
        "3o79xWV36687rg0iwozWtn",  # Top-off driving (mathieu.broillet)
        "37i9dQZF1DX9wC1KY45plY",  # Classic Road Trip Songs (Spotify)
        "1PgdjErYgoSccYxAZiZ9hY",  # Deep (mathieu.broillet)
        "30rl6Pv6S9Sh6tjlpPwMZj",  # Old school (mathieu.broillet)
        "4iQBqMa6Od3oJmuesYbBuj",  # Happyness Overload (mathieu.broillet)
        "10y6jglCdl7sPEWS4t8qP7",  # Liked Songs 2023 (mathieu.broillet)
        "3uMOv3JsNoCS4ZdkfkSE1L",  # Liked Songs 2022 (mathieu.broillet)
        "7MjQETbvJBvgKxSfrwH2CF",  # Beach chills (mathieu.broillet)
        "37i9dQZF1Fa1IIVtEpGUcU",  # Your Top Songs 2023 (Spotify)
        "1jdc0ywbaEJN7x7WLD6NEe",  # Night driving/chill (mathieu.broillet)
        "6F4hHgahE4pGYp28A2gb7z",  # DE? (mathieu.broillet)
        "5GYs4cE4y87KcHPro1zxVo",  # Rap FR (mathieu.broillet)
        "5eJ5L8cS2iGsbEu47YWKvK",  # Old songs and country (mathieu.broillet)
        "37i9dQZF1DWX4UlFW6EJPs",  # The Last of Us Official Playlist (Spotify)
        "47zfjmJN2NNfuW2fGDBkAJ",  # 80s (mathieu.broillet)
        "37i9dQZF1F0sijgNaJdgit",  # Your Top Songs 2022 (Spotify)
        "06iT09jUfY8A3o2RZvkdxu",  # Rap (mathieu.broillet)
        "52f8lzijrd9SqAx9yMMRGD",  # Wednesday Soundtrack 🩸🖤🔪   (Bonbonniere 💿🦄)
        "7lYFPB5NnCCz5q72RAyPZH",  # Chilllll (mathieu.broillet)
        "5QneYTA6ioxQOeJABEADD4",  # Acoustic Guitar Cover Hits (Jean Ravel)
        "5WV0owiuXRi7R7DyD4BjYH",  # Liked Songs 2021 (mathieu.broillet)
        "7v1USquBA2MFiGeYG2Q1LM",  # Liked Songs 2020 (mathieu.broillet)
        "4oRIGiRRdsyzIH88oYUogS",  # Liked Songs 2018-2019 (mathieu.broillet)
        "4uI6iowfYfRdiEina67psq",  # Rock (mathieu.broillet)
    ]
    for playlist in spotify_playlists['items']:
        if playlist['id'] in spotify_playlists_to_save:
            tracks = get_playlist_tracks(playlist['id'])
            for track in tracks:
                trackname = track['track']['name']
                artistname = track['track']['artists'][0]['name']
                albumname = track['track']['album']['name']
                trackid = track['track']['id']
                duration = track['track']['duration_ms'] / 1000

                jellyfin_track = search_jellyfin(trackname, artistname, albumname)
                if jellyfin_track is None:
                    print(f"MISSING: {trackname} - {artistname} ({albumname})")
                    tidal_request = get_tidal_track_id(trackname, artistname, albumname, trackid, duration)
                    if tidal_request is None:
                        print(f"  Not found on Tidal...")
                    else:
                        print(f"  Found on Tidal! Downloading... ({tidal_request[0]})")
                        download_track_from_tidal(f"https://tidal.com/browse/track/{tidal_request[0]}")
                        organise_track(tidal_request[1], tidal_request[2], tidal_request[3])

                print("")

        else:
            # print(f"\"{playlist['id']}\", # {playlist['name']} ({playlist['owner']['display_name']})") # Uncomment to print all playlists in a format that can be copied to the list above (debug)
            continue
