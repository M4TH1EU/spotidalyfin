import datetime
from typing import Optional

from sqlalchemy import DateTime, func, JSON
from sqlalchemy import PrimaryKeyConstraint
from sqlmodel import SQLModel, Column, Field, Enum

from syncphony.types.enums import TaskType, TaskStatus, MatchType


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
    id: int = Field(default=None, primary_key=True)
    type: MatchType = Field(sa_column=Column(Enum(MatchType)))

    spotify_id: Optional[str] = Field(default=None, index=True)
    tidal_id: Optional[str] = Field(default=None, index=True)
    jellyfin_id: Optional[str] = Field(default=None, index=True)
    subsonic_id: Optional[str] = Field(default=None, index=True)


class Tasks(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    type: TaskType = Field(sa_column=Column(Enum(TaskType)))
    status: TaskStatus = Field(sa_column=Column(Enum(TaskStatus)))
    created_at: datetime.datetime = Field(
        default_factory=datetime.datetime.utcnow,
    )
    updated_at: Optional[datetime.datetime] = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )
    details: dict = Field(default_factory=dict, sa_column=Column(JSON))
    logs: Optional[str] = Field(default="")
    warnings: Optional[str] = Field(default="")
    errors: Optional[str] = Field(default="")
