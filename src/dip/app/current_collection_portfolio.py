"""Atomic application execution for the one Current Collection Portfolio."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from types import MappingProxyType
from typing import Protocol

from dip.app.portfolio_concentration import PortfolioConcentrationExecutionEnvelope
from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.portfolio_intelligence.portfolio_concentration import (
    MODULE_ID as CONCENTRATION_MODULE_ID,
    MODULE_VERSION as CONCENTRATION_MODULE_VERSION,
    RULE_SET_VERSION as CONCENTRATION_RULE_SET_VERSION,
    PortfolioConcentrationAnalysisState,
    PortfolioConcentrationOutput,
    validate_portfolio_concentration_output,
    validate_portfolio_concentration_source,
)
from dip.portfolio_intelligence.portfolio_distribution import (
    MODULE_ID as DISTRIBUTION_MODULE_ID,
    MODULE_VERSION as DISTRIBUTION_MODULE_VERSION,
    RULE_SET_VERSION as DISTRIBUTION_RULE_SET_VERSION,
    PortfolioDistributionAnalysisState,
    PortfolioDistributionOutput,
    validate_portfolio_distribution_output,
)

CURRENT_COLLECTION_SCOPE_ID = "current_collection"
PORTFOLIO_EXECUTION_FAILURE_MESSAGE = (
    "Portfolio could not be calculated. Existing saved data has been preserved."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CurrentCollectionContext:
    scope_id: str

    def __post_init__(self) -> None:
        if type(self.scope_id) is not str:
            raise TypeError("scope_id must be a string.")
        if self.scope_id != CURRENT_COLLECTION_SCOPE_ID:
            raise ValueError("scope_id must identify the Current Collection.")

    def __init_subclass__(cls, **kwargs) -> None:
        raise TypeError("CurrentCollectionContext cannot be subclassed.")


@dataclass(frozen=True, slots=True)
class PortfolioDistributionResultSnapshot:
    module_id: str
    module_version: str
    status: IntelligenceStatus
    summary: str
    insights: tuple[str, ...]
    output: PortfolioDistributionOutput
    evidence: tuple[str, ...]
    diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        _snapshot_fields(self, DISTRIBUTION_MODULE_ID, DISTRIBUTION_MODULE_VERSION)
        if type(self.output) is not PortfolioDistributionOutput:
            raise TypeError("Distribution snapshot output is invalid.")

    @property
    def metrics(self):
        return MappingProxyType({"output": self.output})


@dataclass(frozen=True, slots=True)
class PortfolioConcentrationResultSnapshot:
    module_id: str
    module_version: str
    status: IntelligenceStatus
    summary: str
    insights: tuple[str, ...]
    output: PortfolioConcentrationOutput
    evidence: tuple[str, ...]
    diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        _snapshot_fields(self, CONCENTRATION_MODULE_ID, CONCENTRATION_MODULE_VERSION)
        if type(self.output) is not PortfolioConcentrationOutput:
            raise TypeError("Concentration snapshot output is invalid.")

    @property
    def metrics(self):
        return MappingProxyType({"output": self.output})


@dataclass(frozen=True, slots=True)
class CurrentCollectionPortfolio:
    context: CurrentCollectionContext
    distribution: PortfolioDistributionResultSnapshot
    concentration: PortfolioConcentrationResultSnapshot


class CurrentCollectionPortfolioFailureStage(str, Enum):
    DISTRIBUTION = "distribution"
    CONCENTRATION = "concentration"
    EXECUTION_ACTIVE = "execution_active"


@dataclass(frozen=True, slots=True)
class CurrentCollectionPortfolioExecutionOutcome:
    portfolio: CurrentCollectionPortfolio | None
    failure_stage: CurrentCollectionPortfolioFailureStage | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.portfolio is not None and type(self.portfolio) is not CurrentCollectionPortfolio:
            raise TypeError("portfolio must be CurrentCollectionPortfolio or None.")
        if self.failure_stage is None:
            if self.portfolio is None or self.message:
                raise ValueError("A successful outcome requires one Portfolio and no message.")
            return
        if type(self.failure_stage) is not CurrentCollectionPortfolioFailureStage:
            raise TypeError("failure_stage must be a Portfolio failure stage or None.")
        if self.message != PORTFOLIO_EXECUTION_FAILURE_MESSAGE:
            raise ValueError("A failed outcome requires the stable Portfolio failure message.")

    @property
    def succeeded(self) -> bool:
        return self.failure_stage is None


class _DistributionExecution(Protocol):
    def execute(self) -> IntelligenceResult: ...


class _ConcentrationExecution(Protocol):
    def execute_for_distribution_with_source(
        self,
        distribution: IntelligenceResult,
    ) -> PortfolioConcentrationExecutionEnvelope: ...


class CurrentCollectionPortfolioExecutionService:
    """Execute and atomically publish Distribution followed by Concentration."""

    def __init__(self, context, distribution, concentration) -> None:
        if type(context) is not CurrentCollectionContext:
            raise TypeError("context must be CurrentCollectionContext.")
        if not callable(getattr(distribution, "execute", None)):
            raise TypeError("distribution must provide execute().")
        if not callable(
            getattr(concentration, "execute_for_distribution_with_source", None)
        ):
            raise TypeError("concentration must provide the supplied-source boundary.")
        self._context = context
        self._distribution = distribution
        self._concentration = concentration
        self._state_lock = Lock()
        self._execution_active = False
        self._published: CurrentCollectionPortfolio | None = None

    @property
    def context(self) -> CurrentCollectionContext:
        return self._context

    @property
    def published(self) -> CurrentCollectionPortfolio | None:
        with self._state_lock:
            return self._published

    def execute(self) -> CurrentCollectionPortfolioExecutionOutcome:
        active, previous = self._begin_execution()
        if active:
            return self._failure(
                previous, CurrentCollectionPortfolioFailureStage.EXECUTION_ACTIVE
            )
        try:
            try:
                distribution = self._distribution.execute()
                distribution_output = _distribution_result(distribution)
            except Exception:
                return self._failure(
                    previous, CurrentCollectionPortfolioFailureStage.DISTRIBUTION
                )
            try:
                envelope = self._concentration.execute_for_distribution_with_source(
                    distribution
                )
                if type(envelope) is not PortfolioConcentrationExecutionEnvelope:
                    raise TypeError("Concentration returned an invalid execution envelope.")
                if envelope.source is not distribution:
                    raise ValueError("Concentration returned a different Distribution source.")
                concentration_output = _concentration_result(envelope.result)
                validate_portfolio_concentration_source(
                    distribution_output, concentration_output
                )
                portfolio = CurrentCollectionPortfolio(
                    context=self._context,
                    distribution=_distribution_snapshot(
                        distribution, distribution_output
                    ),
                    concentration=_concentration_snapshot(
                        envelope.result, concentration_output
                    ),
                )
            except Exception:
                return self._failure(
                    previous, CurrentCollectionPortfolioFailureStage.CONCENTRATION
                )
            with self._state_lock:
                self._published = portfolio
            return CurrentCollectionPortfolioExecutionOutcome(portfolio)
        finally:
            with self._state_lock:
                self._execution_active = False

    def _begin_execution(self) -> tuple[bool, CurrentCollectionPortfolio | None]:
        with self._state_lock:
            previous = self._published
            if self._execution_active:
                return True, previous
            self._execution_active = True
            return False, previous

    @staticmethod
    def _failure(previous, stage) -> CurrentCollectionPortfolioExecutionOutcome:
        return CurrentCollectionPortfolioExecutionOutcome(
            previous, stage, PORTFOLIO_EXECUTION_FAILURE_MESSAGE
        )


def _distribution_result(value: object) -> PortfolioDistributionOutput:
    output = _result(
        value,
        DISTRIBUTION_MODULE_ID,
        DISTRIBUTION_MODULE_VERSION,
        DISTRIBUTION_RULE_SET_VERSION,
        PortfolioDistributionOutput,
        PortfolioDistributionAnalysisState.INSUFFICIENT_DATA,
    )
    return validate_portfolio_distribution_output(output)


def _concentration_result(value: object) -> PortfolioConcentrationOutput:
    output = _result(
        value,
        CONCENTRATION_MODULE_ID,
        CONCENTRATION_MODULE_VERSION,
        CONCENTRATION_RULE_SET_VERSION,
        PortfolioConcentrationOutput,
        PortfolioConcentrationAnalysisState.INSUFFICIENT_DATA,
    )
    return validate_portfolio_concentration_output(output)


def _result(value, module_id, module_version, rule_set_version, output_type, insufficient):
    if type(value) is not IntelligenceResult:
        raise TypeError("module result must be IntelligenceResult.")
    if value.module_id != module_id or value.module_version != module_version:
        raise ValueError("module result identity/version is unsupported.")
    if type(value.status) is not IntelligenceStatus:
        raise TypeError("module result status must be IntelligenceStatus.")
    if type(value.summary) is not str:
        raise TypeError("module result summary must be a string.")
    for items in (value.insights, value.evidence, value.diagnostics):
        if type(items) is not tuple or any(type(item) is not str for item in items):
            raise TypeError("module result text fields must be tuples of strings.")
    if type(value.metrics) is not dict or tuple(value.metrics) != ("output",):
        raise TypeError("module result must contain only its typed output metric.")
    output = value.metrics["output"]
    if type(output) is not output_type or output.rule_set_version != rule_set_version:
        raise TypeError("module result contains an invalid typed output.")
    expected = (
        IntelligenceStatus.SKIPPED
        if output.analysis_state is insufficient
        else IntelligenceStatus.COMPLETED
    )
    if value.status is not expected:
        raise ValueError("module result status contradicts its analysis state.")
    return output


def _distribution_snapshot(result, output):
    return PortfolioDistributionResultSnapshot(
        result.module_id,
        result.module_version,
        result.status,
        result.summary,
        tuple(result.insights),
        output,
        tuple(result.evidence),
        tuple(result.diagnostics),
    )


def _concentration_snapshot(result, output):
    return PortfolioConcentrationResultSnapshot(
        result.module_id,
        result.module_version,
        result.status,
        result.summary,
        tuple(result.insights),
        output,
        tuple(result.evidence),
        tuple(result.diagnostics),
    )


def _snapshot_fields(value, module_id, module_version):
    if value.module_id != module_id or value.module_version != module_version:
        raise ValueError("snapshot module identity/version is invalid.")
    if type(value.status) is not IntelligenceStatus or type(value.summary) is not str:
        raise TypeError("snapshot status or summary is invalid.")
    for items in (value.insights, value.evidence, value.diagnostics):
        if type(items) is not tuple or any(type(item) is not str for item in items):
            raise TypeError("snapshot text fields must be tuples of strings.")


__all__ = [
    "CURRENT_COLLECTION_SCOPE_ID",
    "PORTFOLIO_EXECUTION_FAILURE_MESSAGE",
    "CurrentCollectionContext",
    "CurrentCollectionPortfolio",
    "CurrentCollectionPortfolioExecutionOutcome",
    "CurrentCollectionPortfolioExecutionService",
    "CurrentCollectionPortfolioFailureStage",
    "PortfolioConcentrationResultSnapshot",
    "PortfolioDistributionResultSnapshot",
]
