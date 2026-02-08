"""Session lifecycle management."""

from __future__ import annotations
from models.session import GameSession


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, GameSession] = {}

    def create_session(self) -> GameSession:
        session = GameSession()
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> GameSession | None:
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> GameSession | None:
        return self._sessions.pop(session_id, None)

    @property
    def active_count(self) -> int:
        return len(self._sessions)
