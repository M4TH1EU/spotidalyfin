def format_path(*parts):
    return "/".join(str(part).replace(" ", "_").lower() for part in parts)


def format_string(string: str) -> str:
    """Format a string by removing content after certain delimiters and stripping whitespace."""
    return string.split('-')[0].strip().split('(')[0].strip().split('[')[0].strip()


def format_artists(artists: list, lower: bool = True) -> list:
    """Format a tidal/spotify list of artist names by handling multiple separators and converting to lowercase."""
    formatted_artists = []
    for artist in artists:
        if isinstance(artist, dict):
            artist = artist.get('name', '')

        separators = ['&', 'and', ',']
        for sep in separators:
            if sep in artist:
                artist = artist.split(sep)
                break

        if isinstance(artist, list):
            formatted_artists.extend(a.strip().lower() if lower else a.strip() for a in artist)
        else:
            formatted_artists.append(artist.strip().lower() if lower else artist.strip())

    return formatted_artists
