from spotidalyfin.db.database import Database
from spotidalyfin.engines.jellyfin_engine import JellyfinManager

if __name__ == '__main__':
    engine = JellyfinManager(
        url="https://jellyfin.broillet.ch",
        db=Database()  # Replace with actual Database instance
    )

    print(engine.get_users())
    print(engine.get_track('2cbfad9d6fe68ace6890bb0bd937b31b'))
