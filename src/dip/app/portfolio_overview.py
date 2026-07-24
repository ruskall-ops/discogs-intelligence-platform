"""Application orchestration for Portfolio Overview."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from dip.decision_intelligence import MarketplaceOpportunityOutput
from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult, IntelligenceStatus
from dip.portfolio_intelligence import (
    OwnedReleaseFact,
    PortfolioOverviewDiagnostic,
    PortfolioOverviewDiagnosticCode,
    PortfolioOverviewInput,
    PortfolioSourceProvenance,
)


class _CollectionProvider(Protocol):
    def owned_portfolio_rows(self) -> list[Any]: ...


class _OpportunityProvider(Protocol):
    def execute(self) -> IntelligenceResult: ...


class _Engine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class PortfolioOverviewExecutionConsistencyError(RuntimeError):
    """Raised when the Portfolio Overview execution boundary is violated."""


class PortfolioOverviewExecutionService:
    """Obtain each source once, normalize it, and execute Portfolio Overview once."""

    def __init__(
        self,
        collection: _CollectionProvider,
        opportunity: _OpportunityProvider,
        engine: _Engine,
        *,
        collection_snapshot_id: int | None = None,
    ) -> None:
        self._collection = collection
        self._opportunity = opportunity
        self._engine = engine
        self._collection_snapshot_id = collection_snapshot_id

    def execute(self) -> IntelligenceResult:
        rows = self._collection.owned_portfolio_rows()
        opportunity = self._opportunity.execute()
        prepared = build_portfolio_overview_input(
            rows,
            opportunity,
            collection_snapshot_id=self._collection_snapshot_id,
        )
        execution = self._engine.execute(
            IntelligenceContext(portfolio_overview_input=prepared)
        )
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise PortfolioOverviewExecutionConsistencyError(
                "Portfolio Overview engine must return exactly one result."
            )
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "portfolio_overview":
            raise PortfolioOverviewExecutionConsistencyError(
                "Portfolio Overview engine returned an unexpected result."
            )
        return result


def build_portfolio_overview_input(
    owned_rows,
    opportunity_result,
    *,
    collection_snapshot_id: int | None = None,
) -> PortfolioOverviewInput:
    """Normalize application-owned rows and validate one Opportunity result."""

    if isinstance(owned_rows, (str, bytes)):
        raise TypeError("owned_rows must be a collection.")
    try:
        rows = tuple(owned_rows)
    except TypeError as exc:
        raise TypeError("owned_rows must be a collection.") from exc

    diagnostics: list[PortfolioOverviewDiagnostic] = []
    quantities: dict[int, int] = {}
    malformed = 0
    for row in rows:
        if not isinstance(row, Mapping):
            malformed += 1
            diagnostics.append(PortfolioOverviewDiagnostic(
                PortfolioOverviewDiagnosticCode.MALFORMED_OWNED_RELEASE_IDENTITY,
                "An owned entry is not a mapping.",
            ))
            continue
        release_id = _positive_integer(row.get("release_id"))
        quantity = _positive_integer(row.get("quantity", 1))
        if release_id is None or quantity is None:
            malformed += 1
            diagnostics.append(PortfolioOverviewDiagnostic(
                PortfolioOverviewDiagnosticCode.MALFORMED_OWNED_RELEASE_IDENTITY,
                "An owned entry has an invalid release identity or quantity.",
                release_id=release_id,
            ))
            continue
        if release_id in quantities:
            quantities[release_id] += quantity
            diagnostics.append(PortfolioOverviewDiagnostic(
                PortfolioOverviewDiagnosticCode.DUPLICATE_OWNED_RELEASE_IDENTITY,
                f"Repeated owned release {release_id} was normalized to one holding.",
                release_id,
            ))
        else:
            quantities[release_id] = quantity

    for release_id in sorted(quantities):
        if quantities[release_id] > 1:
            diagnostics.append(PortfolioOverviewDiagnostic(
                PortfolioOverviewDiagnosticCode.MULTIPLE_OWNED_COPIES_NORMALIZED,
                f"Owned release {release_id} represents {quantities[release_id]} copies.",
                release_id,
            ))
    owned = tuple(OwnedReleaseFact(key, quantities[key]) for key in sorted(quantities))

    output = None
    compatible = False
    if opportunity_result is None:
        diagnostics.append(PortfolioOverviewDiagnostic(
            PortfolioOverviewDiagnosticCode.OPPORTUNITY_SOURCE_MISSING,
            "Marketplace Opportunity result was not supplied.",
        ))
        module_id, module_version = "marketplace_opportunity", None
    elif type(opportunity_result) is not IntelligenceResult:
        diagnostics.append(PortfolioOverviewDiagnostic(
            PortfolioOverviewDiagnosticCode.OPPORTUNITY_SOURCE_INCOMPATIBLE,
            "Marketplace Opportunity source is not an IntelligenceResult.",
        ))
        module_id, module_version = "marketplace_opportunity", None
    else:
        module_id, module_version = opportunity_result.module_id, opportunity_result.module_version
        if isinstance(opportunity_result.metrics, Mapping):
            output = opportunity_result.metrics.get("output")
        compatible = (
            module_id == "marketplace_opportunity"
            and module_version == "1.0"
            and opportunity_result.status is IntelligenceStatus.COMPLETED
            and type(output) is MarketplaceOpportunityOutput
            and output.rule_set_version == "1.0"
        )
        if not compatible:
            diagnostics.append(PortfolioOverviewDiagnostic(
                PortfolioOverviewDiagnosticCode.OPPORTUNITY_SOURCE_INCOMPATIBLE,
                "Marketplace Opportunity module identity, version, status, rule set, or typed output is incompatible.",
            ))

    history_ids = ()
    rule_set_version = None
    releases = ()
    if type(output) is MarketplaceOpportunityOutput:
        rule_set_version = output.rule_set_version
        history_ids = _history_ids(output)
        if compatible:
            releases = output.releases
    provenance = PortfolioSourceProvenance(
        collection_snapshot_id=collection_snapshot_id,
        opportunity_module_id=module_id,
        opportunity_module_version=module_version,
        opportunity_rule_set_version=rule_set_version,
        opportunity_history_snapshot_ids=history_ids,
        compatible=compatible,
        opportunity_diagnostics=(
            tuple(opportunity_result.diagnostics)
            if type(opportunity_result) is IntelligenceResult
            and type(opportunity_result.diagnostics) is tuple
            and all(type(value) is str and value for value in opportunity_result.diagnostics)
            else ()
        ),
    )
    return PortfolioOverviewInput(
        owned,
        releases,
        provenance,
        malformed,
        tuple(diagnostics),
    )


def _history_ids(output: MarketplaceOpportunityOutput) -> tuple[str, ...]:
    seen = []
    for source in output.source_provenance:
        for snapshot_id in source.history_snapshot_ids:
            if snapshot_id not in seen:
                seen.append(snapshot_id)
    return tuple(seen)


def _positive_integer(value) -> int | None:
    if type(value) is int:
        return value if value > 0 else None
    if type(value) is str:
        try:
            normalized = int(value)
        except ValueError:
            return None
        return normalized if normalized > 0 else None
    return None


__all__ = [
    "PortfolioOverviewExecutionConsistencyError",
    "PortfolioOverviewExecutionService",
    "build_portfolio_overview_input",
]
