"""Exact-ID access to the existing individual Collection Decision editor."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


class CollectionDecisionError(RuntimeError):
    """Safe application failure; underlying causes are not public copy."""


@dataclass(frozen=True, slots=True)
class CollectionDecisionRecord:
    release_id: int
    artist: str | None
    title: str | None
    explanation: str
    decision: str
    miss_rating: str
    personal_notes: str
    protected: bool

    def __post_init__(self):
        _identity(self.release_id)
        for value in (self.artist, self.title):
            if value is not None and type(value) is not str:
                raise TypeError("Catalogue labels must be text or None.")
        for value in (self.explanation, self.decision, self.miss_rating, self.personal_notes):
            if type(value) is not str:
                raise TypeError("Editor values must be text.")
        if type(self.protected) is not bool:
            raise TypeError("protected must be boolean.")


class CollectionDecisionRepository(Protocol):
    def collection_decision_for_release(self, release_id: int) -> Mapping[str, object] | None: ...
    def save_decision(self, release_id: int, decision: str, miss_rating: str, notes: str, protected: bool) -> None: ...


def _identity(value):
    if type(value) is not int or value <= 0:
        raise ValueError("release_id must be a positive integer.")


class CollectionDecisionService:
    def __init__(self, repository: CollectionDecisionRepository):
        self._repository = repository

    def load(self, release_id: int) -> CollectionDecisionRecord | None:
        _identity(release_id)
        try:
            row = self._repository.collection_decision_for_release(release_id)
            if row is None:
                return None
            if not isinstance(row, Mapping) or type(row["release_id"]) is not int or row["release_id"] != release_id:
                raise ValueError("Collection Decision identity does not match.")
            if type(row["protected"]) is not int or row["protected"] not in (0, 1):
                raise ValueError("Stored protection is malformed.")
            return CollectionDecisionRecord(
                release_id, row["artist"], row["title"], row["explanation"],
                row["decision"], row["miss_rating"], row["personal_notes"], bool(row["protected"]),
            )
        except Exception as exc:
            raise CollectionDecisionError("Collection Decisions could not be loaded.") from exc

    def save(self, record: CollectionDecisionRecord, decision: str, miss_rating: str, notes: str, protected: bool) -> None:
        if type(record) is not CollectionDecisionRecord:
            raise TypeError("record must be a Collection Decision record.")
        try:
            # Reject a release deleted since opening; do not silently recreate it.
            if self.load(record.release_id) is None:
                raise ValueError("Release no longer exists.")
            self._repository.save_decision(record.release_id, decision, miss_rating, notes, protected)
        except Exception as exc:
            raise CollectionDecisionError("The Collection Decision could not be saved. Your editor remains open.") from exc
