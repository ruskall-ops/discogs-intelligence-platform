"""Application orchestration for preparing intelligence evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol

from dip.intelligence import IntelligenceContext
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)


class IntelligenceEvidenceRepository(Protocol):
    def review_rows(self, *, limit: int) -> list[Any]: ...
    def latest_completed_analysis_run(self) -> Any | None: ...
    def previous_completed_analysis_run(self, before_run_id: int) -> Any | None: ...
    def snapshots_for_analysis_run(self, run_id: int) -> list[Any]: ...
    def collection_evidence_rows(
        self, release_ids: tuple[int, ...]
    ) -> tuple[Mapping[str, Any], ...]: ...


class MarketplaceHistoryQueries(Protocol):
    def previous_snapshot(self, snapshot_id: str) -> MarketplaceSnapshot | None: ...


class IntelligenceContextFactory:
    """Prepare engine evidence outside the dashboard presentation layer."""

    def __init__(
        self,
        repository: IntelligenceEvidenceRepository,
        marketplace_history: MarketplaceHistoryQueries | None = None,
    ) -> None:
        self.repository = repository
        self._marketplace_history = marketplace_history

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

    def build_collector_run(
        self,
        *,
        analysis_run_id: int,
        marketplace_snapshot: MarketplaceSnapshot,
        release_ids: tuple[int, ...],
        captured_at: datetime,
    ) -> IntelligenceContext:
        """Build detached context for one explicit canonical Collector Run."""

        if type(analysis_run_id) is not int or analysis_run_id <= 0:
            raise ValueError("analysis_run_id must be a positive integer.")
        if type(marketplace_snapshot) is not MarketplaceSnapshot:
            raise TypeError("marketplace_snapshot must be a MarketplaceSnapshot.")
        if type(captured_at) is not datetime:
            raise TypeError("captured_at must be a datetime.")
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware.")
        if captured_at.isoformat() != marketplace_snapshot.captured_at.isoformat():
            raise ValueError(
                "captured_at must exactly match marketplace_snapshot.captured_at."
            )
        if marketplace_snapshot.status not in {
            MarketplaceDataStatus.COMPLETE,
            MarketplaceDataStatus.PARTIAL,
        }:
            raise ValueError(
                "Collector Run Intelligence requires complete or partial evidence."
            )
        expected_snapshot_id = f"collector-run-{analysis_run_id}"
        if marketplace_snapshot.snapshot_id != expected_snapshot_id:
            raise ValueError(
                "marketplace_snapshot does not match the Collector Run identity."
            )
        validated_ids = self._validated_release_ids(release_ids)
        observation_ids = tuple(
            value.release_id for value in marketplace_snapshot.release_observations
        )
        if observation_ids != validated_ids:
            raise ValueError(
                "Marketplace observation identities must exactly match release_ids."
            )

        raw_collection = tuple(
            self.repository.collection_evidence_rows(validated_ids)
        )
        collection_by_id: dict[int, Mapping[str, Any]] = {}
        for raw_row in raw_collection:
            if not isinstance(raw_row, Mapping):
                raise TypeError("Collection evidence rows must be mappings.")
            detached = _freeze_mapping(raw_row)
            release_id = detached.get("release_id")
            if (
                type(release_id) is not int
                or release_id <= 0
                or release_id in collection_by_id
            ):
                raise ValueError(
                    "Collection evidence contains an invalid or duplicate identity."
                )
            collection_by_id[release_id] = detached
        returned_ids = tuple(sorted(collection_by_id))
        if returned_ids != validated_ids:
            raise ValueError(
                "Collection evidence identities do not match the fixed run scope."
            )
        collection = tuple(collection_by_id[value] for value in validated_ids)

        marketplace = MappingProxyType(
            {
                observation.release_id: self._marketplace_row(
                    marketplace_snapshot,
                    observation,
                )
                for observation in marketplace_snapshot.release_observations
                if observation.status
                in {
                    MarketplaceDataStatus.COMPLETE,
                    MarketplaceDataStatus.PARTIAL,
                }
            }
        )
        predecessor = self._eligible_predecessor(marketplace_snapshot)
        history_values: dict[str, tuple[Mapping[str, Any], ...]] = {}
        if predecessor is not None:
            history_values[predecessor.snapshot_id] = self._history_rows(
                predecessor,
                collection_by_id,
            )
        history_values[marketplace_snapshot.snapshot_id] = self._history_rows(
            marketplace_snapshot,
            collection_by_id,
        )

        return IntelligenceContext(
            collection=collection,
            marketplace=marketplace,
            history=MappingProxyType(history_values),
            user_context=MappingProxyType({}),
            filters=MappingProxyType({}),
            analysis_run_id=analysis_run_id,
            captured_at=captured_at,
            marketplace_snapshot=marketplace_snapshot,
        )

    def _eligible_predecessor(
        self,
        current: MarketplaceSnapshot,
    ) -> MarketplaceSnapshot | None:
        if self._marketplace_history is None:
            raise RuntimeError(
                "Marketplace History queries are required for Collector Run context."
            )
        seen = {current.snapshot_id}
        candidate_id = current.snapshot_id
        while True:
            candidate = self._marketplace_history.previous_snapshot(candidate_id)
            if candidate is None:
                return None
            if candidate.snapshot_id in seen:
                raise RuntimeError("Marketplace History predecessor traversal cycled.")
            seen.add(candidate.snapshot_id)
            candidate_id = candidate.snapshot_id
            if (
                candidate.status
                in {
                    MarketplaceDataStatus.COMPLETE,
                    MarketplaceDataStatus.PARTIAL,
                }
                and candidate.source == current.source
                and candidate.release_observations
            ):
                return candidate

    @staticmethod
    def _marketplace_row(
        snapshot: MarketplaceSnapshot,
        observation: MarketplaceReleaseObservation,
    ) -> Mapping[str, Any]:
        money = observation.lowest_price
        return _freeze_mapping(
            {
                "release_id": observation.release_id,
                "captured_at": observation.observed_at,
                "marketplace_snapshot_id": snapshot.snapshot_id,
                "marketplace_status": observation.status.value,
                "marketplace_diagnostics": observation.diagnostics,
                "wants": observation.num_wanted,
                "copies_for_sale": observation.num_for_sale,
                "lowest_price": None if money is None else money.amount,
                "currency": None if money is None else money.currency,
            }
        )

    def _history_rows(
        self,
        snapshot: MarketplaceSnapshot,
        collection_by_id: Mapping[int, Mapping[str, Any]],
    ) -> tuple[Mapping[str, Any], ...]:
        rows = []
        for observation in snapshot.release_observations:
            metadata = collection_by_id.get(observation.release_id, {})
            row = dict(metadata)
            row.update(self._marketplace_row(snapshot, observation))
            rows.append(_freeze_mapping(row))
        return tuple(rows)

    @staticmethod
    def _validated_release_ids(values: tuple[int, ...]) -> tuple[int, ...]:
        if type(values) is not tuple or not values:
            raise ValueError("release_ids must be a non-empty tuple.")
        result: list[int] = []
        seen: set[int] = set()
        for index, value in enumerate(values):
            if type(value) is not int:
                raise TypeError(f"release_ids[{index}] must be an integer.")
            if value <= 0:
                raise ValueError(f"release_ids[{index}] must be positive.")
            if value in seen:
                raise ValueError("release_ids must not contain duplicates.")
            seen.add(value)
            result.append(value)
        if tuple(result) != tuple(sorted(result)):
            raise ValueError("release_ids must be ordered by release identity.")
        return tuple(result)

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


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    frozen: dict[str, Any] = {}
    for key, item in value.items():
        if type(key) is not str:
            raise TypeError("Context mapping keys must be strings.")
        frozen[key] = _freeze_value(item)
    return MappingProxyType(frozen)


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_value(item) for item in value)
    return value
