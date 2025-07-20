from spotidalyfin.db.database import Database
from spotidalyfin.engines.jellyfin_engine import JellyfinManager

if __name__ == '__main__':
    engine = JellyfinManager(
        url="https://jellyfin.broillet.ch",
        db=Database()  # Replace with actual Database instance
    )

    print(engine.get_users())
    print(engine.get_album('74151a370400b19ac9f5d018f18a1dd2'))
    print(engine.get_artist('0e9e1928043a888f5f45ba0952863e50'))

    print(engine.get_track('2cbfad9d6fe68ace6890bb0bd937b31b'))

    print(engine.get_playlist('8fda11ea1088480124aef0e80277054e'))

    print(engine.get_user_playlists('6dbbbaa045e34cc597554eb59891d110'))

    print(engine.get_favorite_tracks('6dbbbaa045e34cc597554eb59891d110'))

    print(engine.search_tracks_by_query("i'm still standing"))

    print(engine.search_albums_by_query("too low for zero"))

    print(engine.search_artists_by_query("elton john"))

    print(engine.get_lyrics(engine.get_track('b8da635bdaf1f8a1ed27834d17c066bd')))

    print(engine.create_playlist("Test Playlist", [engine.get_track('b8da635bdaf1f8a1ed27834d17c066bd')], cover_url="https://i.scdn.co/image/ab67616d00001e029acfbf04685635028b45d5b4", user_id='6dbbbaa045e34cc597554eb59891d110'))
