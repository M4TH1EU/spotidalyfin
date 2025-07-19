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

    print(engine.get_favorite_tracks('6dbbbaa045e34cc597554eb59891d110'))
