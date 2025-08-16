from sqlalchemy import PrimaryKeyConstraint
from sqlmodel import SQLModel, Field
from typing import Optional

class SpotifyAccount(SQLModel, table=True):
    username: str = Field(primary_key=True)
    client_id: str
    client_secret: str
    access_token: str
    expires_at: int
    refresh_token: str

class TidalAccount(SQLModel, table=True):
    username: str = Field(primary_key=True)
    access_token: str
    refresh_token: str

class JellyfinAccount(SQLModel, table=True):
    url: str = Field(primary_key=True)
    api: str

class SubsonicAccount(SQLModel, table=True):
    url: str
    username: str
    password: str
    __table_args__ = (
        PrimaryKeyConstraint("url", "username"),
    )

class Match(SQLModel, table=True):
    spotify_id: Optional[str] = Field(default=None, primary_key=True)
    tidal_id: Optional[str] = Field(default=None, primary_key=True)
    jellyfin_id: Optional[str] = Field(default=None, primary_key=True)
    subsonic_id: Optional[str] = Field(default=None, primary_key=True)
