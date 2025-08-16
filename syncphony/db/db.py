from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path

DB_PATH = Path("~/.config/syncphony").expanduser() / "syncphony.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

sqlite_url = f"sqlite:///{DB_PATH}"
engine = create_engine(sqlite_url, echo=True)  # echo=True for SQL logs

# Create all tables
def init_db():
    SQLModel.metadata.create_all(engine)

# Dependency for FastAPI
def get_session():
    with Session(engine) as session:
        yield session