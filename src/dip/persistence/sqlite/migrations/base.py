from __future__ import annotations

from abc import ABC, abstractmethod
import sqlite3


class Migration(ABC):
    """Base class for all database migrations."""

    version: int
    name: str

    @abstractmethod
    def upgrade(self, connection: sqlite3.Connection) -> None:
        """Apply this migration."""
        raise NotImplementedError
