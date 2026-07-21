"""Application orchestration for preparing intelligence evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from dip.intelligence import IntelligenceContext


class IntelligenceEvidenceRepository(Protocol):
    def review_rows(self, *, limit: int) -> list[Any]: ...
    def latest_completed_analysis_run(self) -> Any | None: ...
    def previous_completed_analysis_run(self, before_run_id: int) -> Any | None: ...
    def snapshots_for_analysis_run(self, run_id: int) -> list[Any]: ...


class IntelligenceContextFactory:
    """Prepare engine evidence outside the dashboard presentation layer."""

    def __init__(self, repository: IntelligenceEvidenceRepository) -> None:
        self.repository = repository

    def build(self) -> IntelligenceContext:
        collection = tuple(
            dict(row) for row in self.repository.review_rows(limit=10000)
        )
        collection_by_id = {
            release_id: row
            for row in collection
            if (release_id := self._release_id(row.get("release_id"))) is not None
        }
        latest_run = self.repository.latest_completed_analysis_run()
        history: dict[int, tuple[Mapping[str, Any], ...]] = {}
        marketplace: dict[int, Mapping[str, Any]] = {}
        analysis_run_id = None

        if latest_run is not None:
            analysis_run_id = int(latest_run["id"])
            latest_rows = self._enriched_rows(analysis_run_id, collection_by_id)
            history[analysis_run_id] = latest_rows
            marketplace = {int(row["release_id"]): row for row in latest_rows}
            previous_run = self.repository.previous_completed_analysis_run(
                analysis_run_id
            )
            if previous_run is not None:
                previous_run_id = int(previous_run["id"])
                history[previous_run_id] = self._enriched_rows(
                    previous_run_id,
                    collection_by_id,
                )

        return IntelligenceContext(
            collection=collection,
            marketplace=marketplace,
            history=history,
            analysis_run_id=analysis_run_id,
        )

    def _enriched_rows(
        self,
        run_id: int,
        collection_by_id: Mapping[int, Mapping[str, Any]],
    ) -> tuple[Mapping[str, Any], ...]:
        enriched = []
        for raw_row in self.repository.snapshots_for_analysis_run(run_id):
            row = dict(raw_row)
            release_id = self._release_id(row.get("release_id"))
            if release_id is not None:
                collection_row = collection_by_id.get(release_id, {})
                row.setdefault("artist", collection_row.get("artist"))
                row.setdefault("title", collection_row.get("title"))
                row.setdefault("label", collection_row.get("label"))
            enriched.append(row)
        return tuple(enriched)

    @staticmethod
    def _release_id(value: Any) -> int | None:
        try:
            release_id = int(value)
        except (TypeError, ValueError):
            return None
        return release_id if release_id > 0 and not isinstance(value, bool) else None
