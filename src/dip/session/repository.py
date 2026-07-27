"""Storage-independent repository contract for desktop sessions."""

from __future__ import annotations

from typing import Protocol

from .models import DesktopSession


class SessionRepository(Protocol):
    def get(self) -> DesktopSession | None: ...

    def save(self, session: DesktopSession) -> None: ...


__all__ = ["SessionRepository"]
