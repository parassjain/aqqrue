import uuid
from app.services.csv_manager import CSVManager


class SessionManager:
    """Manages active sessions. In-memory for MVP."""

    def __init__(self):
        self._sessions: dict[str, CSVManager] = {}

    def create_session(self) -> str:
        session_id = uuid.uuid4().hex[:12]
        self._sessions[session_id] = CSVManager(session_id)
        return session_id

    def get_session(self, session_id: str) -> CSVManager | None:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id].cleanup()
            del self._sessions[session_id]

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())


# Global singleton
session_manager = SessionManager()
