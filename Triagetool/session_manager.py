"""
services/session_manager.py
Manages triage session state keyed by thread or user.

Key format:
  Channel thread → "thread:<conversation_id>:<root_activity_id>"
  Direct message → "user:<user_id>"

This allows multiple reporters to run parallel sessions in the same channel
without interfering with each other.
"""

import time
from typing import Optional
from config.questions import TRIAGE_QUESTIONS, TOTAL_STEPS


class Session:
    def __init__(self):
        self.step: int = 0
        self.answers: dict = {}
        self.created_at: float = time.time()
        self.active: bool = True
        # Set by the bot when a channel root-message starts the session
        self.thread_activity_id: Optional[str] = None
        # The verbatim text of the original issue report message
        self.issue_description: Optional[str] = None

    def current_question(self):
        if self.step < TOTAL_STEPS:
            return TRIAGE_QUESTIONS[self.step]
        return None

    def is_complete(self) -> bool:
        return self.step >= TOTAL_STEPS

    def save_answer(self, value: str):
        q = TRIAGE_QUESTIONS[self.step]
        self.answers[q.key] = None if value.strip().lower() == "skip" else value.strip()
        self.step += 1

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "answers": self.answers,
            "created_at": self.created_at,
            "active": self.active,
            "thread_activity_id": self.thread_activity_id,
            "issue_description": self.issue_description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        s = cls()
        s.step = data["step"]
        s.answers = data["answers"]
        s.created_at = data["created_at"]
        s.active = data["active"]
        s.thread_activity_id = data.get("thread_activity_id")
        s.issue_description = data.get("issue_description")
        return s


class SessionManager:
    """
    In-memory session store keyed by thread or user string.
    For production, replace _store get/set/delete with Redis calls.
    """

    def __init__(self, ttl: int = 1800):
        self._store: dict[str, Session] = {}
        self.ttl = ttl  # seconds until a session expires

    def get(self, key: str) -> Optional[Session]:
        session = self._store.get(key)
        if session is None:
            return None
        if time.time() - session.created_at > self.ttl:
            self.reset(key)
            return None
        return session

    def create(self, key: str) -> Session:
        session = Session()
        self._store[key] = session
        return session

    def get_or_create(self, key: str) -> Session:
        session = self.get(key)
        if session is None or not session.active:
            session = self.create(key)
        return session

    def reset(self, key: str):
        self._store.pop(key, None)

    def has_active_session(self, key: str) -> bool:
        session = self.get(key)
        return session is not None and session.active
