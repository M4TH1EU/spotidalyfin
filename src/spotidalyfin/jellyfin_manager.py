# jellyfin_manager.py
import requests

from src.spotidalyfin.constants import JELLYFIN_API_KEY, JELLYFIN_URL
from src.spotidalyfin.utils import format_string


def search_jellyfin(track_name, artist_name, album_name):
    track_name = format_string(track_name)
    artist_name = format_string(artist_name)
    album_name = format_string(album_name)

    request_url = f"{JELLYFIN_URL}/Items?api_key={JELLYFIN_API_KEY}&searchTerm={track_name}&Recursive=True&IncludeItemTypes=Audio&Limit=3"
    response = requests.get(request_url)
    data = response.json()

    if data['TotalRecordCount'] > 0:
        for item in data['Items']:
            if item['Type'] == "Audio" and format_string(item['Name']) == track_name:
                if format_string(item['Artists'][0]) == artist_name and format_string(item['Album']) == album_name:
                    return item['Id']

    return None
