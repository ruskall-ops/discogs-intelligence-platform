"""Read-only current catalogue metadata used for presentation labels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CurrentReleaseMetadata:
    """Detached current artist/title metadata for one stable release identity."""

    release_id: int
    artist: str | None
    title: str | None

    def __post_init__(self) -> None:
        if type(self.release_id) is not int:
            raise TypeError("release_id must be an integer.")
        if self.release_id <= 0:
            raise ValueError("release_id must be positive.")
        for name, value in (("artist", self.artist), ("title", self.title)):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None.")


class CurrentReleaseMetadataRepository(Protocol):
    """Batch-load current catalogue labels without ownership or history joins."""

    def metadata_for_release_ids(
        self,
        release_ids: tuple[int, ...],
    ) -> tuple[CurrentReleaseMetadata, ...]: ...


__all__ = ["CurrentReleaseMetadata", "CurrentReleaseMetadataRepository"]
