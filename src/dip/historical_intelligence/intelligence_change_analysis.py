"""Deterministic change analysis of immutable IntelligenceResult snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.portfolio_decision_intelligence import (
    PortfolioOpportunityAlignmentOutput,
    PortfolioOpportunityMappingCategory,
)


MODULE_ID = "intelligence_change_analysis"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"
SUPPORTED_MODULE_ID = "portfolio_opportunity_alignment"
SUPPORTED_MODULE_VERSION = "1.0"
SUPPORTED_RULE_SET_VERSION = "1.0"


class IntelligenceComparisonState(str, Enum):
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    INCREASED = "increased"
    DECREASED = "decreased"
    MODIFIED = "modified"
    UNKNOWN = "unknown"
    INSUFFICIENT = "insufficient"


class IntelligenceChangeAnalysisReasonCode(str, Enum):
    NO_CHANGE = "no_change"
    ASSESSMENT_CHANGED = "assessment_changed"
    ASSESSMENT_UNCHANGED = "assessment_unchanged"
    EVIDENCE_CHANGED = "evidence_changed"
    EVIDENCE_UNCHANGED = "evidence_unchanged"
    METRIC_CHANGED = "metric_changed"
    RULESET_CHANGED = "ruleset_changed"
    MODULE_VERSION_CHANGED = "module_version_changed"
    PROVENANCE_CHANGED = "provenance_changed"
    REASONS_CHANGED = "reasons_changed"
    DIAGNOSTICS_CHANGED = "diagnostics_changed"
    SOURCE_INCOMPATIBLE = "source_incompatible"
    MODULE_UNSUPPORTED = "module_unsupported"
    INSUFFICIENT_HISTORY = "insufficient_history"
    SNAPSHOT_MISSING = "snapshot_missing"


class IntelligenceChangeAnalysisDiagnosticCode(str, Enum):
    MISSING_PREVIOUS_RESULT = "missing_previous_result"
    MISSING_CURRENT_RESULT = "missing_current_result"
    MALFORMED_RESULT = "malformed_result"
    MODULE_MISMATCH = "module_mismatch"
    UNSUPPORTED_MODULE = "unsupported_module"
    VERSION_MISMATCH = "version_mismatch"
    RULE_SET_MISMATCH = "rule_set_mismatch"
    TYPED_OUTPUT_MISMATCH = "typed_output_mismatch"
    SOURCE_STATUS_INCOMPATIBLE = "source_status_incompatible"
    PORTFOLIO_MISMATCH = "portfolio_mismatch"
    SNAPSHOT_MISMATCH = "snapshot_mismatch"
    SNAPSHOT_IDENTITY_MISSING = "snapshot_identity_missing"
    PROVENANCE_MISMATCH = "provenance_mismatch"
    UNSUPPORTED_COMPARISON = "unsupported_comparison"


@dataclass(frozen=True)
class ComparisonRuleConfiguration:
    rule_set_version: str = RULE_SET_VERSION

    def __post_init__(self):
        if self.rule_set_version != RULE_SET_VERSION:
            raise ValueError("Unsupported Change Analysis rule-set version.")


@dataclass(frozen=True)
class IntelligenceChangeAnalysisDiagnostic:
    code: IntelligenceChangeAnalysisDiagnosticCode
    message: str

    def __post_init__(self):
        if type(self.code) is not IntelligenceChangeAnalysisDiagnosticCode:
            raise TypeError("code must be an IntelligenceChangeAnalysisDiagnosticCode.")
        if type(self.message) is not str or not self.message:
            raise TypeError("message must be a non-empty string.")


@dataclass(frozen=True)
class CategoricalTransition:
    previous: Any
    current: Any
    changed: bool
    comparison_state: IntelligenceComparisonState

    def __post_init__(self):
        expected_changed = self.previous != self.current
        expected_state = IntelligenceComparisonState.MODIFIED if expected_changed else IntelligenceComparisonState.UNCHANGED
        if self.changed is not expected_changed or self.comparison_state is not expected_state:
            raise ValueError("Categorical transition is inconsistent.")


@dataclass(frozen=True)
class MetricTransition:
    metric_id: str
    previous: int | Decimal
    current: int | Decimal
    delta: int | Decimal
    changed: bool
    comparison_state: IntelligenceComparisonState

    def __post_init__(self):
        if type(self.metric_id) is not str or not self.metric_id:
            raise TypeError("metric_id must be a non-empty string.")
        allowed = (int, Decimal)
        if type(self.previous) not in allowed or type(self.current) not in allowed:
            raise TypeError("Metric values must be integers or Decimals.")
        if any(type(value) is Decimal and not value.is_finite() for value in (self.previous, self.current, self.delta)):
            raise ValueError("Metric Decimals must be finite.")
        if type(self.previous) is not type(self.current) or type(self.delta) is not type(self.previous):
            raise TypeError("Metric transition numeric types must match.")
        expected_delta = self.current - self.previous
        expected = (
            IntelligenceComparisonState.INCREASED if expected_delta > 0
            else IntelligenceComparisonState.DECREASED if expected_delta < 0
            else IntelligenceComparisonState.UNCHANGED
        )
        if self.delta != expected_delta or self.changed is not (expected_delta != 0) or self.comparison_state is not expected:
            raise ValueError("Metric transition is inconsistent.")


@dataclass(frozen=True)
class CollectionTransition:
    previous: tuple[Any, ...]
    current: tuple[Any, ...]
    added: tuple[Any, ...]
    removed: tuple[Any, ...]
    changed: bool
    comparison_state: IntelligenceComparisonState

    def __post_init__(self):
        for name in ("previous", "current", "added", "removed"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.changed is not (self.previous != self.current):
            raise ValueError("Collection transition is inconsistent.")
        expected = IntelligenceComparisonState.MODIFIED if self.changed else IntelligenceComparisonState.UNCHANGED
        if self.comparison_state is not expected:
            raise ValueError("Collection comparison state is inconsistent.")


@dataclass(frozen=True)
class ComparisonProvenance:
    previous_module_id: str | None
    current_module_id: str | None
    previous_module_version: str | None
    current_module_version: str | None
    previous_rule_set_version: str | None
    current_rule_set_version: str | None
    portfolio_identity: Any
    previous_collection_snapshot_id: int | None
    current_collection_snapshot_id: int | None
    comparison_rule_set_version: str
    supported_module_id: str


@dataclass(frozen=True)
class ComparisonSummary:
    compared_module_id: str | None
    assessment_changed: bool
    evidence_changed: bool
    metrics_changed: int
    reasons_changed: bool
    diagnostics_changed: bool
    module_version_changed: bool
    rule_set_changed: bool
    provenance_changed: bool
    overall_changed: bool
    comparison_state: IntelligenceComparisonState


@dataclass(frozen=True)
class IntelligenceComparisonOutput:
    rule_set_version: str
    rule_configuration: ComparisonRuleConfiguration
    summary: ComparisonSummary
    assessment: CategoricalTransition
    evidence: CategoricalTransition
    module_version: CategoricalTransition
    source_rule_set: CategoricalTransition
    provenance_transition: CategoricalTransition
    metrics: tuple[MetricTransition, ...]
    supported_dimensions: CollectionTransition
    unusable_dimensions: CollectionTransition
    reasons: CollectionTransition
    diagnostics: CollectionTransition
    reason_codes: tuple[IntelligenceChangeAnalysisReasonCode, ...]
    output_diagnostics: tuple[IntelligenceChangeAnalysisDiagnostic, ...]
    provenance: ComparisonProvenance

    def __post_init__(self):
        for name in ("metrics", "reason_codes", "output_diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.rule_set_version != RULE_SET_VERSION:
            raise ValueError("Unsupported Change Analysis rule set.")
        if self.reason_codes != tuple(sorted(self.reason_codes, key=_reason_order)):
            raise ValueError("Change Analysis reasons must use canonical order.")
        if self.output_diagnostics != tuple(sorted(self.output_diagnostics, key=_diagnostic_order)):
            raise ValueError("Change Analysis diagnostics must use canonical order.")
        changed_metrics = sum(value.changed for value in self.metrics)
        if changed_metrics != self.summary.metrics_changed:
            raise ValueError("Summary metric count is inconsistent.")
        expected_changed = any((
            self.assessment.changed, self.evidence.changed,
            self.module_version.changed, self.source_rule_set.changed,
            self.provenance_transition.changed, self.supported_dimensions.changed,
            self.unusable_dimensions.changed, self.reasons.changed,
            self.diagnostics.changed, changed_metrics,
        ))
        if self.summary.comparison_state is not IntelligenceComparisonState.INSUFFICIENT:
            expected_state = IntelligenceComparisonState.CHANGED if expected_changed else IntelligenceComparisonState.UNCHANGED
            if self.summary.overall_changed is not expected_changed or self.summary.comparison_state is not expected_state:
                raise ValueError("Comparison summary is inconsistent.")


class IntelligenceChangeAnalysis:
    """Compare two completed Alignment results without executing intelligence."""

    module_id = MODULE_ID
    module_version = MODULE_VERSION

    def __init__(self, rules: ComparisonRuleConfiguration = ComparisonRuleConfiguration()):
        if type(rules) is not ComparisonRuleConfiguration:
            raise TypeError("rules must be ComparisonRuleConfiguration.")
        self._rules = rules

    def compare(self, previous: IntelligenceResult | None, current: IntelligenceResult | None) -> IntelligenceResult:
        diagnostics: list[IntelligenceChangeAnalysisDiagnostic] = []
        previous_output = _validate_result(previous, "previous", diagnostics)
        current_output = _validate_result(current, "current", diagnostics)
        if (
            type(previous) is IntelligenceResult
            and type(current) is IntelligenceResult
            and previous.module_id != current.module_id
        ):
            diagnostics.append(_diagnostic(
                IntelligenceChangeAnalysisDiagnosticCode.MODULE_MISMATCH,
                "Previous and current module IDs differ.",
            ))
        if previous_output is not None and current_output is not None:
            previous_snapshot = previous_output.provenance.collection_snapshot_id
            current_snapshot = current_output.provenance.collection_snapshot_id
            if (previous_snapshot is None) != (current_snapshot is None):
                diagnostics.append(_diagnostic(
                    IntelligenceChangeAnalysisDiagnosticCode.SNAPSHOT_IDENTITY_MISSING,
                    "Only one Alignment result supplies collection snapshot identity.",
                ))

        compatible = not diagnostics and previous_output is not None and current_output is not None
        if compatible:
            output = self._compare_valid(previous, current, previous_output, current_output)
        else:
            output = _insufficient(previous, current, previous_output, current_output, self._rules, diagnostics)
        status = (
            IntelligenceStatus.SKIPPED
            if output.summary.comparison_state is IntelligenceComparisonState.INSUFFICIENT
            else IntelligenceStatus.COMPLETED
        )
        return IntelligenceResult(
            MODULE_ID,
            status,
            "Intelligence Change Analysis is insufficient for the supplied results."
            if status is IntelligenceStatus.SKIPPED
            else "Intelligence Change Analysis detected changes."
            if output.summary.overall_changed
            else "Intelligence Change Analysis detected no change.",
            metrics={"output": output},
            diagnostics=tuple(f"{value.code.value}: {value.message}" for value in output.output_diagnostics),
            module_version=MODULE_VERSION,
        )

    def _compare_valid(self, previous_result, current_result, previous, current):
        previous_mapping = _mapping(previous)
        current_mapping = _mapping(current)
        metrics = tuple(
            _metric(metric_id, old, new)
            for metric_id, old, new in (
                ("supportive_share", previous_mapping["supportive"].release_share, current_mapping["supportive"].release_share),
                ("neutral_share", previous_mapping["neutral"].release_share, current_mapping["neutral"].release_share),
                ("limiting_share", previous_mapping["limiting"].release_share, current_mapping["limiting"].release_share),
                ("adverse_share", previous_mapping["adverse"].release_share, current_mapping["adverse"].release_share),
                ("usable_share", _ratio(previous.breadth.usable_releases, previous.breadth.valid_owned_releases), _ratio(current.breadth.usable_releases, current.breadth.valid_owned_releases)),
                ("matched_releases", previous.breadth.matched_releases, current.breadth.matched_releases),
                ("unmatched_releases", previous.breadth.unmatched_releases, current.breadth.unmatched_releases),
                ("owned_releases", previous.breadth.valid_owned_releases, current.breadth.valid_owned_releases),
                ("owned_copies", previous.breadth.total_owned_copies, current.breadth.total_owned_copies),
            )
        )
        assessment = _categorical(previous.summary.assessment, current.summary.assessment)
        evidence = _categorical(previous.summary.evidence_coverage, current.summary.evidence_coverage)
        version = _categorical(previous_result.module_version, current_result.module_version)
        rule_set = _categorical(previous.rule_set_version, current.rule_set_version)
        provenance_transition = _categorical(previous.provenance, current.provenance)
        supported = _collection(previous.provenance.supported_dimensions, current.provenance.supported_dimensions)
        unusable = _collection(previous.provenance.unusable_dimensions, current.provenance.unusable_dimensions)
        reasons = _collection(previous.reason_codes, current.reason_codes)
        diagnostics = _collection(
            previous.diagnostics + tuple(previous_result.diagnostics),
            current.diagnostics + tuple(current_result.diagnostics),
        )
        reason_codes = _reasons(
            assessment, evidence, metrics, version, rule_set,
            provenance_transition, supported, unusable, reasons, diagnostics,
        )
        changed = any((
            assessment.changed, evidence.changed, version.changed, rule_set.changed,
            provenance_transition.changed, supported.changed, unusable.changed,
            reasons.changed, diagnostics.changed, any(value.changed for value in metrics),
        ))
        summary = ComparisonSummary(
            SUPPORTED_MODULE_ID, assessment.changed, evidence.changed,
            sum(value.changed for value in metrics), reasons.changed,
            diagnostics.changed, version.changed, rule_set.changed,
            provenance_transition.changed, changed,
            IntelligenceComparisonState.CHANGED if changed else IntelligenceComparisonState.UNCHANGED,
        )
        provenance = _provenance(previous_result, current_result, previous, current)
        return IntelligenceComparisonOutput(
            RULE_SET_VERSION, self._rules, summary, assessment, evidence, version,
            rule_set, provenance_transition, metrics, supported, unusable, reasons,
            diagnostics, reason_codes, (), provenance,
        )


def _validate_result(result, name, diagnostics):
    missing_code = (
        IntelligenceChangeAnalysisDiagnosticCode.MISSING_PREVIOUS_RESULT
        if name == "previous" else IntelligenceChangeAnalysisDiagnosticCode.MISSING_CURRENT_RESULT
    )
    if result is None:
        diagnostics.append(_diagnostic(missing_code, f"The {name} result was not supplied."))
        return None
    if type(result) is not IntelligenceResult:
        diagnostics.append(_diagnostic(IntelligenceChangeAnalysisDiagnosticCode.MALFORMED_RESULT, f"The {name} result is malformed."))
        return None
    if result.module_id != SUPPORTED_MODULE_ID:
        diagnostics.append(_diagnostic(IntelligenceChangeAnalysisDiagnosticCode.UNSUPPORTED_MODULE, f"The {name} module {result.module_id!r} is unsupported."))
    if result.module_version != SUPPORTED_MODULE_VERSION:
        diagnostics.append(_diagnostic(IntelligenceChangeAnalysisDiagnosticCode.VERSION_MISMATCH, f"The {name} module version {result.module_version!r} is unsupported."))
    output = result.metrics.get("output") if hasattr(result.metrics, "get") else None
    if type(output) is not PortfolioOpportunityAlignmentOutput:
        diagnostics.append(_diagnostic(IntelligenceChangeAnalysisDiagnosticCode.TYPED_OUTPUT_MISMATCH, f"The {name} result lacks typed Alignment output."))
        return None
    if output.rule_set_version != SUPPORTED_RULE_SET_VERSION:
        diagnostics.append(_diagnostic(IntelligenceChangeAnalysisDiagnosticCode.RULE_SET_MISMATCH, f"The {name} rule set {output.rule_set_version!r} is unsupported."))
    snapshot_id = output.provenance.collection_snapshot_id
    if snapshot_id is not None and (type(snapshot_id) is not int or snapshot_id <= 0):
        diagnostics.append(_diagnostic(
            IntelligenceChangeAnalysisDiagnosticCode.SNAPSHOT_MISMATCH,
            f"The {name} collection snapshot identity is malformed.",
        ))
    entries = output.breadth.mapping_entries
    if (
        tuple(value.category for value in entries) != tuple(PortfolioOpportunityMappingCategory)
        or any(type(value.release_share) is not Decimal or not value.release_share.is_finite() for value in entries)
        or any(type(value) is not int or value < 0 for value in (
            output.breadth.valid_owned_releases, output.breadth.total_owned_copies,
            output.breadth.matched_releases, output.breadth.unmatched_releases,
            output.breadth.usable_releases, output.breadth.insufficient_releases,
        ))
    ):
        diagnostics.append(_diagnostic(
            IntelligenceChangeAnalysisDiagnosticCode.UNSUPPORTED_COMPARISON,
            f"The {name} Alignment metrics are not comparison-compatible.",
        ))
    if result.status is not IntelligenceStatus.COMPLETED:
        diagnostics.append(_diagnostic(IntelligenceChangeAnalysisDiagnosticCode.SOURCE_STATUS_INCOMPATIBLE, f"The {name} result is not completed."))
    return output


def _insufficient(previous_result, current_result, previous, current, rules, diagnostics):
    empty = _categorical(None, None)
    collection = _collection((), ())
    reasons = []
    codes = {value.code for value in diagnostics}
    if IntelligenceChangeAnalysisDiagnosticCode.UNSUPPORTED_MODULE in codes:
        reasons.append(IntelligenceChangeAnalysisReasonCode.MODULE_UNSUPPORTED)
    if any(value in codes for value in (
        IntelligenceChangeAnalysisDiagnosticCode.MISSING_PREVIOUS_RESULT,
        IntelligenceChangeAnalysisDiagnosticCode.MISSING_CURRENT_RESULT,
    )):
        reasons.append(IntelligenceChangeAnalysisReasonCode.INSUFFICIENT_HISTORY)
    if IntelligenceChangeAnalysisDiagnosticCode.SNAPSHOT_IDENTITY_MISSING in codes:
        reasons.append(IntelligenceChangeAnalysisReasonCode.SNAPSHOT_MISSING)
    reasons.append(IntelligenceChangeAnalysisReasonCode.SOURCE_INCOMPATIBLE)
    provenance = _provenance(previous_result, current_result, previous, current)
    summary = ComparisonSummary(
        previous_result.module_id if type(previous_result) is IntelligenceResult else
        current_result.module_id if type(current_result) is IntelligenceResult else None,
        False, False, 0, False, False, False, False, False, False,
        IntelligenceComparisonState.INSUFFICIENT,
    )
    return IntelligenceComparisonOutput(
        RULE_SET_VERSION, rules, summary, empty, empty, empty, empty, empty, (),
        collection, collection, collection, collection,
        tuple(sorted(set(reasons), key=_reason_order)),
        tuple(sorted(diagnostics, key=_diagnostic_order)), provenance,
    )


def _provenance(previous_result, current_result, previous, current):
    previous_snapshot = previous.provenance.collection_snapshot_id if previous else None
    current_snapshot = current.provenance.collection_snapshot_id if current else None
    return ComparisonProvenance(
        getattr(previous_result, "module_id", None), getattr(current_result, "module_id", None),
        getattr(previous_result, "module_version", None), getattr(current_result, "module_version", None),
        getattr(previous, "rule_set_version", None), getattr(current, "rule_set_version", None),
        None, previous_snapshot, current_snapshot, RULE_SET_VERSION, SUPPORTED_MODULE_ID,
    )


def _mapping(output):
    return {value.category.value: value for value in output.breadth.mapping_entries}


def _metric(metric_id, previous, current):
    delta = current - previous
    state = (
        IntelligenceComparisonState.INCREASED if delta > 0
        else IntelligenceComparisonState.DECREASED if delta < 0
        else IntelligenceComparisonState.UNCHANGED
    )
    return MetricTransition(metric_id, previous, current, delta, delta != 0, state)


def _categorical(previous, current):
    changed = previous != current
    return CategoricalTransition(
        previous, current, changed,
        IntelligenceComparisonState.MODIFIED if changed else IntelligenceComparisonState.UNCHANGED,
    )


def _collection(previous, current):
    previous, current = tuple(previous), tuple(current)
    added = tuple(value for value in current if value not in previous)
    removed = tuple(value for value in previous if value not in current)
    changed = previous != current
    return CollectionTransition(
        previous, current, added, removed, changed,
        IntelligenceComparisonState.MODIFIED if changed else IntelligenceComparisonState.UNCHANGED,
    )


def _reasons(assessment, evidence, metrics, version, rule_set, provenance, supported, unusable, source_reasons, diagnostics):
    values = [
        IntelligenceChangeAnalysisReasonCode.ASSESSMENT_CHANGED if assessment.changed else IntelligenceChangeAnalysisReasonCode.ASSESSMENT_UNCHANGED,
        IntelligenceChangeAnalysisReasonCode.EVIDENCE_CHANGED if evidence.changed else IntelligenceChangeAnalysisReasonCode.EVIDENCE_UNCHANGED,
    ]
    if any(value.changed for value in metrics):
        values.append(IntelligenceChangeAnalysisReasonCode.METRIC_CHANGED)
    if rule_set.changed:
        values.append(IntelligenceChangeAnalysisReasonCode.RULESET_CHANGED)
    if version.changed:
        values.append(IntelligenceChangeAnalysisReasonCode.MODULE_VERSION_CHANGED)
    if provenance.changed:
        values.append(IntelligenceChangeAnalysisReasonCode.PROVENANCE_CHANGED)
    if source_reasons.changed:
        values.append(IntelligenceChangeAnalysisReasonCode.REASONS_CHANGED)
    if diagnostics.changed:
        values.append(IntelligenceChangeAnalysisReasonCode.DIAGNOSTICS_CHANGED)
    if not any((
        assessment.changed, evidence.changed, any(value.changed for value in metrics),
        version.changed, rule_set.changed, provenance.changed, supported.changed,
        unusable.changed, source_reasons.changed, diagnostics.changed,
    )):
        values.append(IntelligenceChangeAnalysisReasonCode.NO_CHANGE)
    return tuple(sorted(values, key=_reason_order))


def _ratio(numerator, denominator):
    return Decimal("0") if denominator == 0 else Decimal(numerator) / Decimal(denominator)


def _diagnostic(code, message):
    return IntelligenceChangeAnalysisDiagnostic(code, message)


def _reason_order(value):
    return tuple(IntelligenceChangeAnalysisReasonCode).index(value)


def _diagnostic_order(value):
    return tuple(IntelligenceChangeAnalysisDiagnosticCode).index(value.code), value.message


__all__ = [
    "CategoricalTransition", "CollectionTransition", "ComparisonProvenance",
    "ComparisonRuleConfiguration", "ComparisonSummary",
    "IntelligenceChangeAnalysis", "IntelligenceChangeAnalysisDiagnostic",
    "IntelligenceChangeAnalysisDiagnosticCode",
    "IntelligenceChangeAnalysisReasonCode", "IntelligenceComparisonOutput",
    "IntelligenceComparisonState", "MetricTransition",
]
