# jellyfin_manager.py
import requests

from spotidalyfin.utils.formatting import format_string


class JellyfinManager:
    def __init__(self, url, api_key):
        self.url = url.rstrip("/")
        self.api_key = api_key

    def request(self, path, method="GET"):
        try:
            url = self.url + "/" + path.lstrip("/")
            if method == "GET":
                return requests.get(url, headers={"X-Emby-Token": self.api_key}).json()
            elif method == "POST":
                return requests.post(url, headers={"X-Emby-Token": self.api_key}).json()
        except requests.exceptions.RequestException as e:
            # TODO: catch exception
            return

    def search(self, query, limit=5, include_item_types="Audio", recursive=True):
        return self.request(
            f"Items?searchTerm={query}&Recursive={recursive}&IncludeItemTypes={include_item_types}&Limit={limit}")

    def search_album(self, album_name, artist_name):
        album_name = format_string(album_name)
        artist_name = format_string(artist_name)

        response = self.search(f"{album_name} {artist_name}", include_item_types="MusicAlbum")
        if response['TotalRecordCount'] > 0:
            for item in response['Items']:
                # TODO: improve search
                if format_string(item['Name']) == album_name and format_string(item['Artists'][0]) == artist_name:
                    return item['Id']

    def search_track_in_album(self, track_name, album_name, artist_name):
        track_name = format_string(track_name)
        album_name = format_string(album_name)
        artist_name = format_string(artist_name)

        album_id = self.search_album(album_name, artist_name)
        if album_id:
            response = self.request(f"Items/{album_id}/Children")
            if response['TotalRecordCount'] > 0:
                for item in response['Items']:
                    # TODO: improve search
                    if item['Type'] == "Audio" and format_string(item['Name']) == track_name:
                        return item['Id']

    def search_track_by_name(self, track_name, artist_name, album_name):
        track_name = format_string(track_name)
        artist_name = format_string(artist_name)
        album_name = format_string(album_name)

        response = self.search(track_name, include_item_types="Audio")
        if response['TotalRecordCount'] > 0:
            for item in response['Items']:
                # TODO: improve search
                if item['Type'] == "Audio" and format_string(item['Name']) == track_name:
                    if format_string(item['Artists'][0]) == artist_name and format_string(item['Album']) == album_name:
                        return item['Id']

    def does_track_exist(self, spotify_track: dict):
        track_name = spotify_track.get('name', '')
        artist_name = spotify_track.get('artists', [{}])[0].get('name', '')
        album_name = spotify_track.get('album', {}).get('name', '')

        find_by_album = self.search_track_in_album(track_name, album_name, artist_name)
        if find_by_album:
            return find_by_album

        find_by_name = self.search_track_by_name(track_name, artist_name, album_name)
        if find_by_name:
            return find_by_name

        return False
