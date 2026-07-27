"""Application orchestration for safe, user-initiated database backup."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from dip.database_backup import DatabaseBackupManifest


class DatabaseBackupError(RuntimeError):
    """Value-neutral failure raised by the database backup boundary."""


class DatabaseBackupValidationError(DatabaseBackupError):
    """Raised when a requested destination is not safe for publication."""


@dataclass(frozen=True)
class DatabaseBackupResult:
    filename: str

    def __post_init__(self) -> None:
        if (
            type(self.filename) is not str
            or not self.filename
            or Path(self.filename).name != self.filename
        ):
            raise ValueError("filename must be a safe filename.")


class DatabaseBackupAdapter(Protocol):
    @property
    def source_path(self) -> Path: ...

    def create_backup(self, destination: Path) -> DatabaseBackupManifest: ...

    def verify_backup(
        self,
        backup_path: Path,
        *,
        expected_manifest: DatabaseBackupManifest,
    ) -> None: ...


class DatabaseBackupService:
    """Create, verify, and atomically publish one complete SQLite backup."""

    def __init__(self, adapter: DatabaseBackupAdapter) -> None:
        self._adapter = adapter

    def backup(
        self,
        destination: Path,
        *,
        overwrite: bool = False,
    ) -> DatabaseBackupResult:
        if not isinstance(destination, Path):
            raise TypeError("destination must be a Path.")
        if type(overwrite) is not bool:
            raise TypeError("overwrite must be a boolean.")

        target = destination.expanduser().absolute()
        self._validate_destination(target, overwrite=overwrite)
        temporary: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
            )
            temporary = Path(temporary_name)
            os.close(descriptor)
            expected = self._adapter.create_backup(temporary)
            self._adapter.verify_backup(
                temporary,
                expected_manifest=expected,
            )
            self._validate_destination(target, overwrite=overwrite)
            os.replace(temporary, target)
            temporary = None
            return DatabaseBackupResult(target.name)
        except DatabaseBackupError:
            raise
        except Exception as exc:
            raise DatabaseBackupError("Database backup could not be created.") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def _validate_destination(self, target: Path, *, overwrite: bool) -> None:
        if target.suffix.lower() != ".sqlite3":
            raise DatabaseBackupValidationError(
                "Choose a filename ending in .sqlite3."
            )
        parent = target.parent
        if not parent.exists() or not parent.is_dir():
            raise DatabaseBackupValidationError(
                "Choose an existing destination folder."
            )
        if target.is_symlink():
            raise DatabaseBackupValidationError(
                "A symbolic link cannot be used as a backup destination."
            )
        if target.exists() and target.is_dir():
            raise DatabaseBackupValidationError(
                "The backup destination must be a file."
            )
        if self._same_source(target):
            raise DatabaseBackupValidationError(
                "The live database cannot be used as the backup destination."
            )
        if target.exists() and not overwrite:
            raise DatabaseBackupValidationError(
                "The backup destination already exists."
            )

    def _same_source(self, target: Path) -> bool:
        source = self._adapter.source_path.expanduser().resolve()
        try:
            if target.exists() and source.exists():
                return os.path.samefile(source, target)
        except OSError:
            pass
        return target.resolve(strict=False) == source

    def validate_destination(
        self,
        destination: Path,
        *,
        overwrite: bool = False,
    ) -> None:
        if not isinstance(destination, Path):
            raise TypeError("destination must be a Path.")
        if type(overwrite) is not bool:
            raise TypeError("overwrite must be a boolean.")
        self._validate_destination(
            destination.expanduser().absolute(),
            overwrite=overwrite,
        )

__all__ = [
    "DatabaseBackupAdapter",
    "DatabaseBackupError",
    "DatabaseBackupManifest",
    "DatabaseBackupResult",
    "DatabaseBackupService",
    "DatabaseBackupValidationError",
]
