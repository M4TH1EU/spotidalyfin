import musicbrainzngs

from syncphony.types import Album
from syncphony.types.compare import compare_musicbrainz_release_album


def search_album(album: Album):
    musicbrainzngs.set_useragent("syncphony", "0.1")

    try:
        result = musicbrainzngs.search_releases(
            artist=album.artist,
            release=album.name,
            barcode=album.barcode if album.barcode else None,
            date=album.release_date.year if album.release_date else None,
            limit=5
        )
        release_list = result.get("release-list", [])
        scored_releases_list = [(r, compare_musicbrainz_release_album(r, album)) for r in
                                release_list]
        best_release, best_release_score = max(scored_releases_list, key=lambda x: x[1], default=(None, 0))

        return None


    except Exception as e:
        print(f"Error searching for album {album.name} by {album.artist}: {e}")
        return []
