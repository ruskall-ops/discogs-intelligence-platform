"""Application boundary for loading and saving desktop sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from dip.session import (
    DesktopSession,
    DesktopSessionCapture,
    SESSION_FORMAT_VERSION,
    SessionPersistenceError,
    SessionRepository,
)


class SessionRestorationService:
    def __init__(
        self,
        repository: SessionRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def load(self) -> DesktopSession | None:
        try:
            return self._repository.get()
        except SessionPersistenceError:
            raise
        except Exception as exc:
            raise SessionPersistenceError(
                "Desktop session could not be loaded."
            ) from exc

    def save(self, capture: DesktopSessionCapture) -> DesktopSession:
        if type(capture) is not DesktopSessionCapture:
            raise TypeError("capture must be DesktopSessionCapture.")
        saved_at = self._clock()
        if type(saved_at) is not datetime:
            raise TypeError("Session clock must return a datetime.")
        if saved_at.tzinfo is None or saved_at.utcoffset() is None:
            raise ValueError("Session clock must return a timezone-aware datetime.")
        session = DesktopSession(
            SESSION_FORMAT_VERSION,
            saved_at.astimezone(timezone.utc),
            capture.active_project_id,
            capture.window_width,
            capture.window_height,
            capture.window_x,
            capture.window_y,
            capture.top_level_destination,
            capture.collection_review_destination,
            capture.observation_source,
            capture.queue_filter,
            capture.decision_priority_filter,
            capture.decision_state_filter,
            capture.selected_observation,
            capture.selected_queue_item_id,
            capture.selected_decision_release_id,
        )
        try:
            self._repository.save(session)
        except SessionPersistenceError:
            raise
        except Exception as exc:
            raise SessionPersistenceError(
                "Desktop session could not be saved."
            ) from exc
        return session


__all__ = ["SessionRestorationService"]
