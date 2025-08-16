from typing import Dict
from uuid import uuid4

from tidalapi import Session

TEMP_SESSION_STORE: Dict[str, Session] = {}


def store_temp_session(session: Session) -> str:
    session_id = str(uuid4())
    TEMP_SESSION_STORE[session_id] = session
    return session_id


def get_temp_session(session_id: str) -> Session:
    return TEMP_SESSION_STORE.get(session_id)


def remove_temp_session(session_id: str):
    TEMP_SESSION_STORE.pop(session_id, None)
