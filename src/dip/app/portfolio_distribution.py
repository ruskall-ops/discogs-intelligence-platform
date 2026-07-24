"""Application orchestration and normalization for Portfolio Distribution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult
from dip.portfolio_intelligence import (
    PortfolioDistributionDiagnostic,
    PortfolioDistributionDiagnosticCode,
    PortfolioDistributionInput,
    PortfolioDistributionProvenance,
    PortfolioDistributionRuleConfiguration,
    PortfolioReleaseMetadataFact,
)


class _CollectionProvider(Protocol):
    def owned_portfolio_metadata_rows(self) -> list[Any]: ...


class _Engine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class PortfolioDistributionExecutionConsistencyError(RuntimeError):
    """Raised when the Portfolio Distribution execution boundary is violated."""


class PortfolioDistributionExecutionService:
    def __init__(
        self,
        collection: _CollectionProvider,
        engine: _Engine,
        *,
        collection_snapshot_id: int | None = None,
        rules: PortfolioDistributionRuleConfiguration = PortfolioDistributionRuleConfiguration(),
    ) -> None:
        if type(rules) is not PortfolioDistributionRuleConfiguration:
            raise TypeError("rules must be PortfolioDistributionRuleConfiguration.")
        self._collection = collection
        self._engine = engine
        self._collection_snapshot_id = collection_snapshot_id
        self._rules = rules

    def execute(self) -> IntelligenceResult:
        rows = self._collection.owned_portfolio_metadata_rows()
        prepared = build_portfolio_distribution_input(
            rows,
            collection_snapshot_id=self._collection_snapshot_id,
            rules=self._rules,
        )
        execution = self._engine.execute(
            IntelligenceContext(portfolio_distribution_input=prepared)
        )
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise PortfolioDistributionExecutionConsistencyError(
                "Portfolio Distribution engine must return exactly one result."
            )
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "portfolio_distribution":
            raise PortfolioDistributionExecutionConsistencyError(
                "Portfolio Distribution engine returned an unexpected result."
            )
        return result


def build_portfolio_distribution_input(
    owned_rows,
    *,
    collection_snapshot_id: int | None = None,
    rules: PortfolioDistributionRuleConfiguration = PortfolioDistributionRuleConfiguration(),
) -> PortfolioDistributionInput:
    if type(rules) is not PortfolioDistributionRuleConfiguration:
        raise TypeError("rules must be PortfolioDistributionRuleConfiguration.")
    if isinstance(owned_rows, (str, bytes)):
        raise TypeError("owned_rows must be a collection.")
    try:
        rows = tuple(owned_rows)
    except TypeError as exc:
        raise TypeError("owned_rows must be a collection.") from exc

    facts: dict[int, PortfolioReleaseMetadataFact] = {}
    conflicted: set[int] = set()
    diagnostics: list[PortfolioDistributionDiagnostic] = []
    malformed = 0
    for row in rows:
        if not isinstance(row, Mapping):
            malformed += 1
            diagnostics.append(_diagnostic(
                PortfolioDistributionDiagnosticCode.MALFORMED_RELEASE_IDENTITY,
                "An ownership metadata row is not a mapping.",
            ))
            continue
        release_id = _positive_integer(row.get("release_id"))
        quantity = _positive_integer(row.get("quantity"))
        if release_id is None:
            malformed += 1
            diagnostics.append(_diagnostic(
                PortfolioDistributionDiagnosticCode.MALFORMED_RELEASE_IDENTITY,
                "An ownership metadata row has an invalid release identity.",
            ))
            continue
        if quantity is None:
            malformed += 1
            diagnostics.append(_diagnostic(
                PortfolioDistributionDiagnosticCode.INVALID_OWNERSHIP_QUANTITY,
                f"Release {release_id} has an invalid ownership quantity.",
                release_id,
            ))
            continue
        artist = _text(row.get("artist"))
        label = _text(row.get("label"))
        format_value = _text(row.get("format"))
        year, invalid_year = _year(row.get("released"), rules)
        if invalid_year:
            diagnostics.append(_diagnostic(
                PortfolioDistributionDiagnosticCode.INVALID_RELEASE_YEAR,
                f"Release {release_id} has an invalid canonical release year.",
                release_id,
            ))
        candidate = PortfolioReleaseMetadataFact(
            release_id, quantity, artist, label, format_value, year,
        )
        existing = facts.get(release_id)
        if existing is None and release_id not in conflicted:
            facts[release_id] = candidate
            continue
        if release_id in conflicted:
            continue
        if (
            existing.artist, existing.label, existing.format, existing.release_year
        ) != (
            candidate.artist, candidate.label, candidate.format, candidate.release_year
        ):
            facts.pop(release_id)
            conflicted.add(release_id)
            malformed += 1
            diagnostics.append(_diagnostic(
                PortfolioDistributionDiagnosticCode.CONFLICTING_DUPLICATE_METADATA,
                f"Repeated release {release_id} has conflicting canonical metadata and was excluded.",
                release_id,
            ))
            continue
        facts[release_id] = PortfolioReleaseMetadataFact(
            release_id, existing.quantity + candidate.quantity,
            existing.artist, existing.label, existing.format, existing.release_year,
        )
        diagnostics.append(_diagnostic(
            PortfolioDistributionDiagnosticCode.DUPLICATE_OWNERSHIP_ROW_NORMALIZED,
            f"Repeated release {release_id} was normalized to one holding.",
            release_id,
        ))
    return PortfolioDistributionInput(
        tuple(facts[key] for key in sorted(facts)),
        malformed,
        PortfolioDistributionProvenance(collection_snapshot_id),
        tuple(sorted(diagnostics, key=_diagnostic_order)),
    )


def _positive_integer(value):
    if type(value) is int:
        return value if value > 0 else None
    if type(value) is str:
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def _text(value):
    if type(value) is not str:
        return None
    normalized = value.strip()
    return normalized or None


def _year(value, rules):
    if value is None or (type(value) is str and not value.strip()):
        return None, False
    parsed = _positive_integer(value.strip() if type(value) is str else value)
    if parsed is None or not rules.minimum_release_year <= parsed <= rules.maximum_release_year:
        return None, True
    return parsed, False


def _diagnostic(code, message, release_id=None):
    return PortfolioDistributionDiagnostic(code, message, release_id)


def _diagnostic_order(value):
    return (
        tuple(PortfolioDistributionDiagnosticCode).index(value.code),
        -1 if value.release_id is None else value.release_id,
        value.message,
    )


__all__ = [
    "PortfolioDistributionExecutionConsistencyError",
    "PortfolioDistributionExecutionService",
    "build_portfolio_distribution_input",
]
