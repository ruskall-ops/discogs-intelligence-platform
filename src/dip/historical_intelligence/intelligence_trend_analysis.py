"""Deterministic trends across an explicitly ordered Change Analysis sequence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from dip.intelligence import IntelligenceResult, IntelligenceStatus

from .intelligence_change_analysis import (
    IntelligenceComparisonOutput,
    IntelligenceComparisonState,
)


MODULE_ID = "intelligence_trend_analysis"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"
CHANGE_MODULE_ID = "intelligence_change_analysis"
SOURCE_MODULE_ID = "portfolio_opportunity_alignment"


class IntelligenceTrendClassification(str, Enum):
    STABLE = "stable"
    CONSISTENTLY_INCREASING = "consistently_increasing"
    CONSISTENTLY_DECREASING = "consistently_decreasing"
    NET_INCREASING = "net_increasing"
    NET_DECREASING = "net_decreasing"
    REVERSING = "reversing"
    OSCILLATING = "oscillating"
    MIXED = "mixed"
    MODIFIED = "modified"
    INSUFFICIENT = "insufficient"


class IntelligenceTrendOverallPattern(str, Enum):
    STABLE = "stable"
    NUMERIC_MOVEMENT = "numeric_movement"
    CATEGORICAL_MODIFICATION = "categorical_modification"
    MIXED_MOVEMENT = "mixed_movement"
    INSUFFICIENT = "insufficient"


class IntelligenceTrendEvidenceCoverage(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class IntelligenceTrendReasonCode(str, Enum):
    COMPLETE_TREND_EVIDENCE = "complete_trend_evidence"
    PARTIAL_TREND_EVIDENCE = "partial_trend_evidence"
    LIMITED_TREND_EVIDENCE = "limited_trend_evidence"
    INSUFFICIENT_TREND_EVIDENCE = "insufficient_trend_evidence"
    MINIMUM_HISTORY_AVAILABLE = "minimum_history_available"
    INSUFFICIENT_CHANGE_RESULTS = "insufficient_change_results"
    UNSUPPORTED_CHANGE_MODULE = "unsupported_change_module"
    UNSUPPORTED_CHANGE_VERSION = "unsupported_change_version"
    UNSUPPORTED_CHANGE_RULE_SET = "unsupported_change_rule_set"
    UNSUPPORTED_SOURCE_MODULE = "unsupported_source_module"
    SOURCE_SEMANTICS_CHANGED = "source_semantics_changed"
    DISCONTINUOUS_SNAPSHOT_CHAIN = "discontinuous_snapshot_chain"
    DUPLICATE_TRANSITION = "duplicate_transition"
    REVERSED_TRANSITION_ORDER = "reversed_transition_order"
    BRANCHED_TRANSITION_SEQUENCE = "branched_transition_sequence"
    ASSESSMENT_STABLE = "assessment_stable"
    ASSESSMENT_MODIFIED = "assessment_modified"
    EVIDENCE_STABLE = "evidence_stable"
    EVIDENCE_MODIFIED = "evidence_modified"
    NUMERIC_METRICS_STABLE = "numeric_metrics_stable"
    NUMERIC_METRICS_CHANGED = "numeric_metrics_changed"
    REVERSAL_PRESENT = "reversal_present"
    OSCILLATION_PRESENT = "oscillation_present"
    OVERALL_TREND_STABLE = "overall_trend_stable"
    OVERALL_NUMERIC_MOVEMENT = "overall_numeric_movement"
    OVERALL_CATEGORICAL_MODIFICATION = "overall_categorical_modification"
    OVERALL_MIXED_MOVEMENT = "overall_mixed_movement"
    OVERALL_TREND_INSUFFICIENT = "overall_trend_insufficient"


class IntelligenceTrendDiagnosticCode(str, Enum):
    MISSING_INPUT_SEQUENCE = "missing_input_sequence"
    INSUFFICIENT_COMPARISON_COUNT = "insufficient_comparison_count"
    NULL_COMPARISON_RESULT = "null_comparison_result"
    WRONG_MODULE_ID = "wrong_module_id"
    UNSUPPORTED_CHANGE_VERSION = "unsupported_change_version"
    UNSUPPORTED_CHANGE_RULE_SET = "unsupported_change_rule_set"
    MALFORMED_TYPED_OUTPUT = "malformed_typed_output"
    UNUSABLE_RESULT_STATUS = "unusable_result_status"
    UNSUPPORTED_SOURCE_MODULE = "unsupported_source_module"
    SOURCE_SEMANTICS_CHANGED = "source_semantics_changed"
    INVALID_COMPARISON_IDENTITY = "invalid_comparison_identity"
    DUPLICATE_TRANSITION = "duplicate_transition"
    REVERSED_TRANSITION_ORDER = "reversed_transition_order"
    BRANCHED_TRANSITION_SEQUENCE = "branched_transition_sequence"
    DISCONTINUOUS_SNAPSHOT_CHAIN = "discontinuous_snapshot_chain"
    DISCONTINUOUS_VALUE_CHAIN = "discontinuous_value_chain"
    INCOMPATIBLE_METRIC_DEFINITION = "incompatible_metric_definition"
    INVALID_NUMERIC_TRANSITION = "invalid_numeric_transition"
    DELTA_RECONCILIATION_FAILURE = "delta_reconciliation_failure"


@dataclass(frozen=True)
class IntelligenceTrendRuleConfiguration:
    minimum_comparison_count: int = 2
    minimum_observation_count: int = 3
    strict_consistent_direction: bool = True
    minimum_sustained_transitions_before_reversal: int = 2
    minimum_directional_transitions_for_oscillation: int = 3
    minimum_direction_changes_for_oscillation: int = 2
    unchanged_ignored_for_direction_changes: bool = True

    def __post_init__(self):
        if any(type(getattr(self, name)) is not int for name in (
            "minimum_comparison_count", "minimum_observation_count",
            "minimum_sustained_transitions_before_reversal",
            "minimum_directional_transitions_for_oscillation",
            "minimum_direction_changes_for_oscillation",
        )):
            raise TypeError("Trend rule counts must be integers.")
        if self.minimum_comparison_count < 2 or self.minimum_observation_count != self.minimum_comparison_count + 1:
            raise ValueError("Trend rules require at least two comparisons and one more observation.")
        if type(self.strict_consistent_direction) is not bool or type(self.unchanged_ignored_for_direction_changes) is not bool:
            raise TypeError("Trend rule switches must be booleans.")


@dataclass(frozen=True)
class IntelligenceTrendDiagnostic:
    code: IntelligenceTrendDiagnosticCode
    message: str
    sequence_position: int | None = None


@dataclass(frozen=True)
class IntelligenceStateTransitionFrequency:
    previous: Any
    current: Any
    occurrence_count: int
    first_occurrence_position: int
    latest_occurrence_position: int


@dataclass(frozen=True)
class IntelligenceCategoricalTrend:
    trend_id: str
    first_value: Any
    latest_value: Any
    observed_values: tuple[Any, ...]
    distinct_values: tuple[Any, ...]
    transition_states: tuple[IntelligenceComparisonState, ...]
    transition_frequencies: tuple[IntelligenceStateTransitionFrequency, ...]
    changed_transition_count: int
    unchanged_transition_count: int
    stable: bool
    classification: IntelligenceTrendClassification

    def __post_init__(self):
        for name in ("observed_values", "distinct_values", "transition_states", "transition_frequencies"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True)
class IntelligenceNumericMetricTrend:
    metric_id: str
    numeric_type: str
    first_value: int | Decimal
    latest_value: int | Decimal
    minimum_value: int | Decimal
    maximum_value: int | Decimal
    net_delta: int | Decimal
    transition_states: tuple[IntelligenceComparisonState, ...]
    transition_deltas: tuple[int | Decimal, ...]
    increase_count: int
    decrease_count: int
    unchanged_count: int
    insufficient_count: int
    direction_change_count: int
    longest_increasing_run: int
    longest_decreasing_run: int
    longest_unchanged_run: int
    final_transition_state: IntelligenceComparisonState
    classification: IntelligenceTrendClassification
    observation_count: int
    transition_count: int

    def __post_init__(self):
        object.__setattr__(self, "transition_states", tuple(self.transition_states))
        object.__setattr__(self, "transition_deltas", tuple(self.transition_deltas))
        if sum(self.transition_deltas) != self.net_delta:
            raise ValueError("Metric transition deltas do not reconcile.")


@dataclass(frozen=True)
class IntelligencePresenceItemTrend:
    identity: Any
    occurrence_count: int
    transition_count: int
    first_seen_position: int
    last_seen_position: int
    latest_present: bool
    continuously_present: bool


@dataclass(frozen=True)
class IntelligencePresenceTrend:
    first_values: tuple[Any, ...]
    latest_values: tuple[Any, ...]
    continuously_present: tuple[Any, ...]
    intermittently_present: tuple[Any, ...]
    added_values: tuple[Any, ...]
    removed_values: tuple[Any, ...]
    observation_count: int
    items: tuple[IntelligencePresenceItemTrend, ...] = ()


@dataclass(frozen=True)
class IntelligenceDimensionTrend:
    first_supported: tuple[str, ...]
    latest_supported: tuple[str, ...]
    always_supported: tuple[str, ...]
    added_dimensions: tuple[str, ...]
    removed_dimensions: tuple[str, ...]
    first_unusable: tuple[str, ...]
    latest_unusable: tuple[str, ...]
    became_usable: tuple[str, ...]
    became_unusable: tuple[str, ...]
    supported_transitions: tuple[Any, ...]
    unusable_transitions: tuple[Any, ...]


@dataclass(frozen=True)
class IntelligenceTrendProvenance:
    change_module_ids: tuple[str, ...]
    change_module_versions: tuple[str, ...]
    change_rule_set_versions: tuple[str, ...]
    compared_source_module_id: str | None
    compared_source_module_version: str | None
    compared_source_rule_set_version: str | None
    portfolio_identity: Any
    first_snapshot_identity: int | None
    latest_snapshot_identity: int | None
    ordered_snapshot_chain: tuple[int | None, ...]
    input_comparison_count: int
    represented_observation_count: int
    trend_module_version: str
    trend_rule_set_version: str


@dataclass(frozen=True)
class IntelligenceTrendAnalysisSummary:
    compared_module_id: str | None
    comparison_count: int
    observation_count: int
    assessment_stable: bool
    evidence_stable: bool
    numeric_metrics_analysed: int
    numeric_metrics_stable: int
    numeric_metrics_changed: int
    categorical_trends_modified: int
    reasons_added: int
    reasons_removed: int
    diagnostics_added: int
    diagnostics_removed: int
    dimensions_added: int
    dimensions_removed: int
    overall_pattern: IntelligenceTrendOverallPattern
    evidence_coverage: IntelligenceTrendEvidenceCoverage


@dataclass(frozen=True)
class IntelligenceTrendAnalysisOutput:
    rule_set_version: str
    rule_configuration: IntelligenceTrendRuleConfiguration
    summary: IntelligenceTrendAnalysisSummary
    assessment_trend: IntelligenceCategoricalTrend
    evidence_trend: IntelligenceCategoricalTrend
    numeric_metric_trends: tuple[IntelligenceNumericMetricTrend, ...]
    reason_trend: IntelligencePresenceTrend
    diagnostic_trend: IntelligencePresenceTrend
    dimension_trend: IntelligenceDimensionTrend
    source_evidence_states: tuple[Any, ...]
    reason_codes: tuple[IntelligenceTrendReasonCode, ...]
    diagnostics: tuple[IntelligenceTrendDiagnostic, ...]
    provenance: IntelligenceTrendProvenance

    def __post_init__(self):
        for name in ("numeric_metric_trends", "source_evidence_states", "reason_codes", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.rule_set_version != RULE_SET_VERSION:
            raise ValueError("Unsupported Trend Analysis rule set.")
        if self.reason_codes != tuple(sorted(self.reason_codes, key=lambda value: tuple(IntelligenceTrendReasonCode).index(value))):
            raise ValueError("Trend reasons must use canonical order.")
        if self.diagnostics != tuple(sorted(self.diagnostics, key=_diagnostic_order)):
            raise ValueError("Trend diagnostics must use canonical order.")


class IntelligenceTrendAnalysis:
    module_id = MODULE_ID
    module_version = MODULE_VERSION

    def __init__(self, rules: IntelligenceTrendRuleConfiguration = IntelligenceTrendRuleConfiguration()):
        if type(rules) is not IntelligenceTrendRuleConfiguration:
            raise TypeError("rules must be IntelligenceTrendRuleConfiguration.")
        self._rules = rules

    def analyse(self, results) -> IntelligenceResult:
        sequence = tuple(results) if results is not None else ()
        outputs, diagnostics = _validate_sequence(sequence, self._rules)
        output = (
            _analyse(sequence, outputs, self._rules)
            if not diagnostics else _insufficient(sequence, outputs, self._rules, diagnostics)
        )
        status = IntelligenceStatus.SKIPPED if output.summary.evidence_coverage is IntelligenceTrendEvidenceCoverage.INSUFFICIENT else IntelligenceStatus.COMPLETED
        return IntelligenceResult(
            MODULE_ID, status,
            "Intelligence Trend Analysis has insufficient compatible change history."
            if status is IntelligenceStatus.SKIPPED
            else f"Intelligence Trend Analysis observed {output.summary.overall_pattern.value.replace('_', ' ')}.",
            metrics={"output": output},
            diagnostics=tuple(f"{value.code.value}: {value.message}" for value in output.diagnostics),
            module_version=MODULE_VERSION,
        )


def _validate_sequence(sequence, rules):
    diagnostics, outputs = [], []
    if not sequence:
        diagnostics.append(_d(IntelligenceTrendDiagnosticCode.MISSING_INPUT_SEQUENCE, "No Change Analysis results were supplied."))
    if len(sequence) < rules.minimum_comparison_count:
        diagnostics.append(_d(IntelligenceTrendDiagnosticCode.INSUFFICIENT_COMPARISON_COUNT, "At least two Change Analysis results are required."))
    for position, result in enumerate(sequence):
        output = None
        if result is None:
            diagnostics.append(_d(IntelligenceTrendDiagnosticCode.NULL_COMPARISON_RESULT, "A Change Analysis result is missing.", position))
        elif type(result) is not IntelligenceResult:
            diagnostics.append(_d(IntelligenceTrendDiagnosticCode.MALFORMED_TYPED_OUTPUT, "A supplied value is not an IntelligenceResult.", position))
        else:
            if result.module_id != CHANGE_MODULE_ID:
                diagnostics.append(_d(IntelligenceTrendDiagnosticCode.WRONG_MODULE_ID, "Only intelligence_change_analysis is supported.", position))
            if result.module_version != "1.0":
                diagnostics.append(_d(IntelligenceTrendDiagnosticCode.UNSUPPORTED_CHANGE_VERSION, "Change Analysis module version is unsupported.", position))
            output = result.metrics.get("output") if hasattr(result.metrics, "get") else None
            if type(output) is not IntelligenceComparisonOutput:
                diagnostics.append(_d(IntelligenceTrendDiagnosticCode.MALFORMED_TYPED_OUTPUT, "Change Analysis typed output is missing.", position))
                output = None
            else:
                if output.rule_set_version != "1.0":
                    diagnostics.append(_d(IntelligenceTrendDiagnosticCode.UNSUPPORTED_CHANGE_RULE_SET, "Change Analysis rule set is unsupported.", position))
                if result.status is not IntelligenceStatus.COMPLETED:
                    diagnostics.append(_d(IntelligenceTrendDiagnosticCode.UNUSABLE_RESULT_STATUS, "Change Analysis result is not completed.", position))
                if output.summary.compared_module_id != SOURCE_MODULE_ID or output.provenance.supported_module_id != SOURCE_MODULE_ID:
                    diagnostics.append(_d(IntelligenceTrendDiagnosticCode.UNSUPPORTED_SOURCE_MODULE, "Compared source module is unsupported.", position))
                if (
                    output.provenance.previous_module_version != "1.0"
                    or output.provenance.current_module_version != "1.0"
                    or output.provenance.previous_rule_set_version != "1.0"
                    or output.provenance.current_rule_set_version != "1.0"
                    or output.module_version.changed or output.source_rule_set.changed
                ):
                    diagnostics.append(_d(IntelligenceTrendDiagnosticCode.SOURCE_SEMANTICS_CHANGED, "Source module or rule-set semantics are incompatible.", position))
        outputs.append(output)
    if len(outputs) >= 2 and all(value is not None for value in outputs):
        metric_ids = tuple(value.metric_id for value in outputs[0].metrics)
        transitions = set()
        for position, output in enumerate(outputs):
            identity = (output.provenance.previous_collection_snapshot_id, output.provenance.current_collection_snapshot_id)
            comparison_identity = identity if None not in identity else _value_identity(output)
            if comparison_identity in transitions:
                diagnostics.append(_d(IntelligenceTrendDiagnosticCode.DUPLICATE_TRANSITION, "A duplicate snapshot transition was supplied.", position))
            transitions.add(comparison_identity)
            if tuple(value.metric_id for value in output.metrics) != metric_ids:
                diagnostics.append(_d(IntelligenceTrendDiagnosticCode.INCOMPATIBLE_METRIC_DEFINITION, "Metric identities or order differ.", position))
            if position:
                previous = outputs[position - 1]
                if previous.provenance.current_collection_snapshot_id != output.provenance.previous_collection_snapshot_id:
                    if output.provenance.previous_collection_snapshot_id == previous.provenance.previous_collection_snapshot_id:
                        code, message = IntelligenceTrendDiagnosticCode.BRANCHED_TRANSITION_SEQUENCE, "The supplied transition sequence branches."
                    elif output.provenance.current_collection_snapshot_id == previous.provenance.previous_collection_snapshot_id:
                        code, message = IntelligenceTrendDiagnosticCode.REVERSED_TRANSITION_ORDER, "The supplied transitions are reversed or form a loop."
                    else:
                        code, message = IntelligenceTrendDiagnosticCode.DISCONTINUOUS_SNAPSHOT_CHAIN, "Snapshot transitions do not form a continuous supplied chain."
                    if None not in (
                        previous.provenance.current_collection_snapshot_id,
                        output.provenance.previous_collection_snapshot_id,
                    ):
                        diagnostics.append(_d(code, message, position))
                if not _continuous(previous, output):
                    diagnostics.append(_d(IntelligenceTrendDiagnosticCode.DISCONTINUOUS_VALUE_CHAIN, "Visible transition values do not form a continuous chain.", position))
    return tuple(outputs), tuple(sorted(diagnostics, key=_diagnostic_order))


def _value_identity(output):
    return (
        output.assessment.previous, output.assessment.current,
        output.evidence.previous, output.evidence.current,
        tuple((value.metric_id, value.previous, value.current) for value in output.metrics),
    )


def _continuous(previous, current):
    if previous.assessment.current != current.assessment.previous or previous.evidence.current != current.evidence.previous:
        return False
    if previous.supported_dimensions.current != current.supported_dimensions.previous or previous.unusable_dimensions.current != current.unusable_dimensions.previous:
        return False
    return all(left.current == right.previous for left, right in zip(previous.metrics, current.metrics, strict=True))


def _analyse(sequence, outputs, rules):
    assessment = _categorical("assessment", tuple(value.assessment for value in outputs))
    evidence = _categorical("evidence", tuple(value.evidence for value in outputs))
    metrics = tuple(_numeric(tuple(value.metrics[index] for value in outputs), rules) for index in range(len(outputs[0].metrics)))
    reasons = _presence(tuple(value.reasons for value in outputs))
    source_diagnostics = _presence(tuple(value.diagnostics for value in outputs))
    dimensions = _dimensions(outputs)
    numeric_changed = sum(value.classification is not IntelligenceTrendClassification.STABLE for value in metrics)
    categorical_changed = sum((
        not assessment.stable, not evidence.stable,
        outputs[0].reasons.previous != outputs[-1].reasons.current,
        outputs[0].diagnostics.previous != outputs[-1].diagnostics.current,
        dimensions.first_supported != dimensions.latest_supported,
        dimensions.first_unusable != dimensions.latest_unusable,
    ))
    pattern = (
        IntelligenceTrendOverallPattern.STABLE if not numeric_changed and not categorical_changed
        else IntelligenceTrendOverallPattern.NUMERIC_MOVEMENT if numeric_changed and not categorical_changed
        else IntelligenceTrendOverallPattern.CATEGORICAL_MODIFICATION if categorical_changed and not numeric_changed
        else IntelligenceTrendOverallPattern.MIXED_MOVEMENT
    )
    coverage = (
        IntelligenceTrendEvidenceCoverage.LIMITED if not metrics
        else IntelligenceTrendEvidenceCoverage.PARTIAL
        if any(value.diagnostics for value in sequence)
        else IntelligenceTrendEvidenceCoverage.COMPLETE
    )
    summary = IntelligenceTrendAnalysisSummary(
        SOURCE_MODULE_ID, len(outputs), len(outputs) + 1, assessment.stable,
        evidence.stable, len(metrics), len(metrics) - numeric_changed, numeric_changed,
        categorical_changed, len(reasons.added_values), len(reasons.removed_values),
        len(source_diagnostics.added_values), len(source_diagnostics.removed_values),
        len(dimensions.added_dimensions), len(dimensions.removed_dimensions),
        pattern, coverage,
    )
    reason_codes = _reasons(summary, metrics)
    return IntelligenceTrendAnalysisOutput(
        RULE_SET_VERSION, rules, summary, assessment, evidence, metrics, reasons,
        source_diagnostics, dimensions,
        tuple(value.evidence.previous for value in outputs) + (outputs[-1].evidence.current,),
        reason_codes, (), _provenance(sequence, outputs),
    )


def _numeric(transitions, rules):
    first, latest = transitions[0].previous, transitions[-1].current
    states = tuple(value.comparison_state for value in transitions)
    deltas = tuple(value.delta for value in transitions)
    observations = (first,) + tuple(value.current for value in transitions)
    directions = tuple(value for value in states if value in {IntelligenceComparisonState.INCREASED, IntelligenceComparisonState.DECREASED})
    changes = sum(left is not right for left, right in zip(directions, directions[1:]))
    classification = _numeric_classification(states, directions, changes, first, latest, rules)
    return IntelligenceNumericMetricTrend(
        transitions[0].metric_id, "decimal" if type(first) is Decimal else "integer",
        first, latest, min(observations), max(observations), latest - first, states,
        deltas, states.count(IntelligenceComparisonState.INCREASED),
        states.count(IntelligenceComparisonState.DECREASED),
        states.count(IntelligenceComparisonState.UNCHANGED),
        states.count(IntelligenceComparisonState.INSUFFICIENT), changes,
        _longest(states, IntelligenceComparisonState.INCREASED),
        _longest(states, IntelligenceComparisonState.DECREASED),
        _longest(states, IntelligenceComparisonState.UNCHANGED),
        states[-1], classification, len(observations), len(states),
    )


def _numeric_classification(states, directions, changes, first, latest, rules):
    if any(value not in {IntelligenceComparisonState.INCREASED, IntelligenceComparisonState.DECREASED, IntelligenceComparisonState.UNCHANGED} for value in states):
        return IntelligenceTrendClassification.INSUFFICIENT
    if all(value is IntelligenceComparisonState.UNCHANGED for value in states):
        return IntelligenceTrendClassification.STABLE
    if all(value is IntelligenceComparisonState.INCREASED for value in states):
        return IntelligenceTrendClassification.CONSISTENTLY_INCREASING
    if all(value is IntelligenceComparisonState.DECREASED for value in states):
        return IntelligenceTrendClassification.CONSISTENTLY_DECREASING
    sustained = rules.minimum_sustained_transitions_before_reversal
    prior_run = 0
    if len(directions) >= 2 and directions[-1] is not directions[-2]:
        prior_direction = directions[-2]
        for value in reversed(directions[:-1]):
            if value is not prior_direction:
                break
            prior_run += 1
    if prior_run >= sustained:
        return IntelligenceTrendClassification.REVERSING
    if len(directions) >= rules.minimum_directional_transitions_for_oscillation and changes >= rules.minimum_direction_changes_for_oscillation:
        return IntelligenceTrendClassification.OSCILLATING
    if latest > first:
        return IntelligenceTrendClassification.NET_INCREASING
    if latest < first:
        return IntelligenceTrendClassification.NET_DECREASING
    return IntelligenceTrendClassification.MIXED


def _categorical(trend_id, transitions):
    observed = (transitions[0].previous,) + tuple(value.current for value in transitions)
    states = tuple(value.comparison_state for value in transitions)
    frequencies = []
    pairs = tuple((value.previous, value.current) for value in transitions)
    for position, pair in enumerate(pairs):
        if pair not in pairs[:position]:
            positions = tuple(index for index, value in enumerate(pairs) if value == pair)
            frequencies.append(IntelligenceStateTransitionFrequency(pair[0], pair[1], len(positions), positions[0], positions[-1]))
    changed = sum(value is IntelligenceComparisonState.MODIFIED for value in states)
    return IntelligenceCategoricalTrend(
        trend_id, observed[0], observed[-1], observed, tuple(dict.fromkeys(observed)),
        states, tuple(frequencies), changed, len(states) - changed, changed == 0,
        IntelligenceTrendClassification.STABLE if changed == 0 else IntelligenceTrendClassification.MODIFIED,
    )


def _presence(transitions):
    observations = (transitions[0].previous,) + tuple(value.current for value in transitions)
    universe = tuple(dict.fromkeys(value for observation in observations for value in observation))
    items = tuple(
        IntelligencePresenceItemTrend(
            value,
            sum(value in observation for observation in observations),
            sum((value in left) != (value in right) for left, right in zip(observations, observations[1:])),
            next(index for index, observation in enumerate(observations) if value in observation),
            max(index for index, observation in enumerate(observations) if value in observation),
            value in observations[-1],
            all(value in observation for observation in observations),
        )
        for value in universe
    )
    return IntelligencePresenceTrend(
        observations[0], observations[-1],
        tuple(value for value in universe if all(value in observation for observation in observations)),
        tuple(value for value in universe if any(value in observation for observation in observations) and not all(value in observation for observation in observations)),
        tuple(value for value in universe if value not in observations[0] and value in observations[-1]),
        tuple(value for value in universe if value in observations[0] and value not in observations[-1]),
        len(observations), items,
    )


def _dimensions(outputs):
    supported = tuple(value.supported_dimensions for value in outputs)
    unusable = tuple(value.unusable_dimensions for value in outputs)
    first_s, latest_s = supported[0].previous, supported[-1].current
    first_u, latest_u = unusable[0].previous, unusable[-1].current
    observations = (first_s,) + tuple(value.current for value in supported)
    universe = tuple(dict.fromkeys(value for item in observations for value in item))
    return IntelligenceDimensionTrend(
        first_s, latest_s, tuple(value for value in universe if all(value in item for item in observations)),
        tuple(value for value in latest_s if value not in first_s),
        tuple(value for value in first_s if value not in latest_s),
        first_u, latest_u, tuple(value for value in first_u if value not in latest_u),
        tuple(value for value in latest_u if value not in first_u), supported, unusable,
    )


def _reasons(summary, metrics):
    values = [
        {
            IntelligenceTrendEvidenceCoverage.COMPLETE: IntelligenceTrendReasonCode.COMPLETE_TREND_EVIDENCE,
            IntelligenceTrendEvidenceCoverage.PARTIAL: IntelligenceTrendReasonCode.PARTIAL_TREND_EVIDENCE,
            IntelligenceTrendEvidenceCoverage.LIMITED: IntelligenceTrendReasonCode.LIMITED_TREND_EVIDENCE,
            IntelligenceTrendEvidenceCoverage.INSUFFICIENT: IntelligenceTrendReasonCode.INSUFFICIENT_TREND_EVIDENCE,
        }[summary.evidence_coverage],
        IntelligenceTrendReasonCode.MINIMUM_HISTORY_AVAILABLE,
        IntelligenceTrendReasonCode.ASSESSMENT_STABLE if summary.assessment_stable else IntelligenceTrendReasonCode.ASSESSMENT_MODIFIED,
        IntelligenceTrendReasonCode.EVIDENCE_STABLE if summary.evidence_stable else IntelligenceTrendReasonCode.EVIDENCE_MODIFIED,
        IntelligenceTrendReasonCode.NUMERIC_METRICS_STABLE if not summary.numeric_metrics_changed else IntelligenceTrendReasonCode.NUMERIC_METRICS_CHANGED,
    ]
    if any(value.classification is IntelligenceTrendClassification.REVERSING for value in metrics):
        values.append(IntelligenceTrendReasonCode.REVERSAL_PRESENT)
    if any(value.classification is IntelligenceTrendClassification.OSCILLATING for value in metrics):
        values.append(IntelligenceTrendReasonCode.OSCILLATION_PRESENT)
    values.append({
        IntelligenceTrendOverallPattern.STABLE: IntelligenceTrendReasonCode.OVERALL_TREND_STABLE,
        IntelligenceTrendOverallPattern.NUMERIC_MOVEMENT: IntelligenceTrendReasonCode.OVERALL_NUMERIC_MOVEMENT,
        IntelligenceTrendOverallPattern.CATEGORICAL_MODIFICATION: IntelligenceTrendReasonCode.OVERALL_CATEGORICAL_MODIFICATION,
        IntelligenceTrendOverallPattern.MIXED_MOVEMENT: IntelligenceTrendReasonCode.OVERALL_MIXED_MOVEMENT,
        IntelligenceTrendOverallPattern.INSUFFICIENT: IntelligenceTrendReasonCode.OVERALL_TREND_INSUFFICIENT,
    }[summary.overall_pattern])
    return tuple(sorted(values, key=lambda value: tuple(IntelligenceTrendReasonCode).index(value)))


def _insufficient(sequence, outputs, rules, diagnostics):
    empty_categorical = IntelligenceCategoricalTrend(
        "unavailable", None, None, (), (), (), (), 0, 0, False, IntelligenceTrendClassification.INSUFFICIENT,
    )
    empty_presence = IntelligencePresenceTrend((), (), (), (), (), (), 0)
    empty_dimensions = IntelligenceDimensionTrend((), (), (), (), (), (), (), (), (), (), ())
    summary = IntelligenceTrendAnalysisSummary(
        None, len(sequence), len(sequence) + 1 if sequence else 0, False, False,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        IntelligenceTrendOverallPattern.INSUFFICIENT, IntelligenceTrendEvidenceCoverage.INSUFFICIENT,
    )
    reasons = tuple(sorted({
        IntelligenceTrendReasonCode.INSUFFICIENT_TREND_EVIDENCE,
        IntelligenceTrendReasonCode.INSUFFICIENT_CHANGE_RESULTS if len(sequence) < rules.minimum_comparison_count else IntelligenceTrendReasonCode.SOURCE_SEMANTICS_CHANGED,
        IntelligenceTrendReasonCode.OVERALL_TREND_INSUFFICIENT,
    }, key=lambda value: tuple(IntelligenceTrendReasonCode).index(value)))
    return IntelligenceTrendAnalysisOutput(
        RULE_SET_VERSION, rules, summary, empty_categorical, empty_categorical, (),
        empty_presence, empty_presence, empty_dimensions, (), reasons,
        tuple(sorted(diagnostics, key=_diagnostic_order)), _provenance(sequence, tuple(value for value in outputs if value is not None)),
    )


def _provenance(sequence, outputs):
    first = outputs[0] if outputs else None
    last = outputs[-1] if outputs else None
    chain = (
        (first.provenance.previous_collection_snapshot_id,) +
        tuple(value.provenance.current_collection_snapshot_id for value in outputs)
        if first else ()
    )
    return IntelligenceTrendProvenance(
        tuple(getattr(value, "module_id", "") for value in sequence),
        tuple(getattr(value, "module_version", "") for value in sequence),
        tuple(value.rule_set_version for value in outputs),
        first.summary.compared_module_id if first else None,
        first.provenance.previous_module_version if first else None,
        first.provenance.previous_rule_set_version if first else None,
        first.provenance.portfolio_identity if first else None,
        chain[0] if chain else None, chain[-1] if chain else None, chain,
        len(sequence), len(sequence) + 1 if sequence else 0, MODULE_VERSION, RULE_SET_VERSION,
    )


def _longest(values, target):
    longest = current = 0
    for value in values:
        current = current + 1 if value is target else 0
        longest = max(longest, current)
    return longest


def _d(code, message, position=None):
    return IntelligenceTrendDiagnostic(code, message, position)


def _diagnostic_order(value):
    return tuple(IntelligenceTrendDiagnosticCode).index(value.code), -1 if value.sequence_position is None else value.sequence_position, value.message


__all__ = [name for name in globals() if name.startswith("IntelligenceTrend")]
