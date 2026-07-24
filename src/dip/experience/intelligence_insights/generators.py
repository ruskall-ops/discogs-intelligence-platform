"""Explicit deterministic insight generators over immutable ViewModels."""

from dip.experience.history_explorer import HistoricalSnapshotViewModel
from dip.experience.intelligence_change_analysis import (
    IntelligenceChangeAnalysisDetailState,
    IntelligenceChangeAnalysisViewModel,
)
from dip.experience.intelligence_trend_analysis import (
    IntelligenceTrendAnalysisDetailState,
    IntelligenceTrendAnalysisViewModel,
)

from .models import (
    IntelligenceInsight,
    IntelligenceInsightCategory as Category,
    IntelligenceInsightCollection,
    IntelligenceInsightCollectionState as State,
    IntelligenceInsightEvidence,
    IntelligenceInsightPriority as Priority,
    IntelligenceInsightSource,
    IntelligenceInsightType as InsightType,
)


class SnapshotInsightGenerator:
    def generate(self, view_model):
        if view_model is None:
            return IntelligenceInsightCollection(State.NO_SNAPSHOT, Category.SNAPSHOT, (), "No snapshot.")
        if type(view_model) is not HistoricalSnapshotViewModel:
            raise TypeError("view_model must be HistoricalSnapshotViewModel.")
        source = IntelligenceInsightSource(
            type(view_model).__name__, view_model.module_id, view_model.module_version,
            view_model.rule_set_version, view_model.snapshot_identity,
        )
        shared = (view_model.reasons, view_model.diagnostics, view_model.provenance)
        insights = [
            _insight(
                "Snapshot assessment observed.",
                "The supplied snapshot exposes one assessment.",
                (("Assessment", view_model.assessment),), source, shared,
                Priority.IMPORTANT, Category.SNAPSHOT, InsightType.ASSESSMENT,
            ),
            _insight(
                "Snapshot evidence observed.",
                "The supplied snapshot exposes one evidence state.",
                (("Evidence", view_model.evidence),), source, shared,
                Priority.IMPORTANT, Category.SNAPSHOT, InsightType.EVIDENCE,
            ),
        ]
        if view_model.metrics:
            insights.append(_insight(
                "Snapshot metrics are present.", "The supplied snapshot exposes metric evidence.",
                (("Metrics", *view_model.metrics),), source, shared,
                Priority.INFORMATIONAL, Category.SNAPSHOT, InsightType.NUMERIC_METRIC,
            ))
        if view_model.reasons:
            insights.append(_insight(
                "Snapshot reasons are present.", "The supplied reasons remain visible.",
                (("Reasons", *view_model.reasons),), source, shared,
                Priority.INFORMATIONAL, Category.SNAPSHOT, InsightType.REASON,
            ))
        if view_model.diagnostics:
            insights.append(_insight(
                "Snapshot diagnostics are present.", "The supplied diagnostics remain visible.",
                (("Diagnostics", *view_model.diagnostics),), source, shared,
                Priority.INFORMATIONAL, Category.SNAPSHOT, InsightType.DIAGNOSTIC,
            ))
        if view_model.configuration is not None:
            insights.append(_insight(
                "Snapshot configuration is available.", "The supplied configuration remains visible.",
                (("Configuration", view_model.configuration),), source, shared,
                Priority.INFORMATIONAL, Category.SNAPSHOT, InsightType.CONFIGURATION,
            ))
        insights.append(_insight(
            "Snapshot provenance is available.", "The snapshot source identity remains inspectable.",
            (("Provenance", view_model.provenance), ("Snapshot identity", view_model.snapshot_identity)),
            source, shared, Priority.INFORMATIONAL, Category.SNAPSHOT, InsightType.PROVENANCE,
        ))
        return _available(Category.SNAPSHOT, insights)


class ChangeInsightGenerator:
    def generate(self, view_model):
        if view_model is None:
            return IntelligenceInsightCollection(State.NO_CHANGE, Category.CHANGE, (), "No change.")
        if type(view_model) is not IntelligenceChangeAnalysisViewModel:
            raise TypeError("view_model must be IntelligenceChangeAnalysisViewModel.")
        if view_model.state is IntelligenceChangeAnalysisDetailState.UNAVAILABLE:
            return IntelligenceInsightCollection(State.UNAVAILABLE, Category.CHANGE, (), "Change insights unavailable.")
        if view_model.output is None:
            return IntelligenceInsightCollection(State.EMPTY, Category.CHANGE, (), "No change insights.")
        output = view_model.output
        source = IntelligenceInsightSource(
            type(view_model).__name__, output.summary.compared_module_id,
            output.provenance.current_module_version, output.rule_set_version,
            output.provenance.current_collection_snapshot_id,
        )
        shared = (output.reason_codes, output.output_diagnostics, output.provenance)
        insights = [
            _insight(
                "Observed values changed." if output.summary.overall_changed else "Observed values remained unchanged.",
                "The supplied Change Analysis summary is preserved.",
                (("Comparison state", output.summary.comparison_state), ("Changed", output.summary.overall_changed)),
                source, shared, Priority.IMPORTANT, Category.CHANGE, InsightType.OVERALL,
            ),
            _transition_insight("Assessment", output.assessment, source, shared, InsightType.ASSESSMENT),
            _transition_insight("Evidence", output.evidence, source, shared, InsightType.EVIDENCE),
        ]
        insights.extend(
            _insight(
                f"{_label(value.metric_id)} {value.comparison_state.value}.",
                "The supplied numeric transition remains visible without reinterpretation.",
                (("Previous", value.previous), ("Current", value.current), ("Delta", value.delta), ("State", value.comparison_state)),
                source, shared, Priority.IMPORTANT,
                Category.CHANGE, InsightType.NUMERIC_METRIC,
            )
            for value in output.metrics
        )
        for label, transition in (
            ("Supported dimensions", output.supported_dimensions),
            ("Unavailable dimensions", output.unusable_dimensions),
        ):
            insights.append(_insight(
                f"{label} changed." if transition.changed else f"{label} remained unchanged.",
                "The supplied dimension transition remains visible.",
                (("Transition", transition),),
                source, shared, Priority.INFORMATIONAL, Category.CHANGE, InsightType.DIMENSION,
            ))
        insights.extend(_collection_change_insights("Reason", output.reasons, source, shared, InsightType.REASON))
        insights.extend(_collection_change_insights("Diagnostic", output.diagnostics, source, shared, InsightType.DIAGNOSTIC))
        insights.append(_insight(
            "Change provenance is available.", "The supplied comparison provenance remains inspectable.",
            (("Provenance", output.provenance),), source, shared,
            Priority.INFORMATIONAL, Category.CHANGE, InsightType.PROVENANCE,
        ))
        return _available(Category.CHANGE, insights)


class TrendInsightGenerator:
    def generate(self, view_model):
        if view_model is None:
            return IntelligenceInsightCollection(State.NO_TREND, Category.TREND, (), "No trend.")
        if type(view_model) is not IntelligenceTrendAnalysisViewModel:
            raise TypeError("view_model must be IntelligenceTrendAnalysisViewModel.")
        if view_model.state is IntelligenceTrendAnalysisDetailState.UNAVAILABLE:
            return IntelligenceInsightCollection(State.UNAVAILABLE, Category.TREND, (), "Trend insights unavailable.")
        if view_model.output is None:
            return IntelligenceInsightCollection(State.EMPTY, Category.TREND, (), "No trend insights.")
        output = view_model.output
        source = IntelligenceInsightSource(
            type(view_model).__name__, output.summary.compared_module_id,
            output.provenance.compared_source_module_version,
            output.rule_set_version, output.provenance.latest_snapshot_identity,
        )
        shared = (output.reason_codes, output.diagnostics, output.provenance)
        insights = [
            _insight(
                f"Observed history shows {_label(output.summary.overall_pattern.value)}.",
                "The supplied overall historical pattern remains visible.",
                (("Overall pattern", output.summary.overall_pattern), ("Evidence", output.summary.evidence_coverage)),
                source, shared, Priority.IMPORTANT, Category.TREND, InsightType.OVERALL,
            ),
            _categorical_trend_insight("Assessment", output.assessment_trend, source, shared, InsightType.ASSESSMENT),
            _categorical_trend_insight("Evidence", output.evidence_trend, source, shared, InsightType.EVIDENCE),
        ]
        insights.extend(
            _insight(
                f"{_label(value.metric_id)} is {_label(value.classification.value)}.",
                "The supplied metric history and classification remain visible.",
                (("Observed values", value.first_value, value.latest_value), ("Transition states", *value.transition_states), ("Net delta", value.net_delta), ("Classification", value.classification)),
                source, shared, Priority.IMPORTANT,
                Category.TREND, InsightType.NUMERIC_METRIC,
            )
            for value in output.numeric_metric_trends
        )
        insights.append(_insight(
            "Dimension history is available.", "The supplied dimension changes remain visible.",
            (("Dimension trend", output.dimension_trend),),
            source, shared, Priority.INFORMATIONAL, Category.TREND, InsightType.DIMENSION,
        ))
        insights.extend(_presence_insights("Reason", output.reason_trend, source, shared, InsightType.REASON))
        insights.extend(_presence_insights("Diagnostic", output.diagnostic_trend, source, shared, InsightType.DIAGNOSTIC))
        insights.append(_insight(
            "Trend configuration is available.", "The supplied trend rules remain visible.",
            (("Configuration", output.rule_configuration),), source, shared,
            Priority.INFORMATIONAL, Category.TREND, InsightType.CONFIGURATION,
        ))
        insights.append(_insight(
            "Trend provenance is available.", "The supplied historical sequence identity remains inspectable.",
            (("Provenance", output.provenance),), source, shared,
            Priority.INFORMATIONAL, Category.TREND, InsightType.PROVENANCE,
        ))
        return _available(Category.TREND, insights)


def _transition_insight(label, transition, source, shared, insight_type):
    return _insight(
        f"{label} changed." if transition.changed else f"{label} remained unchanged.",
        f"The supplied {label.lower()} transition remains visible.",
        (("Previous", transition.previous), ("Current", transition.current), ("State", transition.comparison_state)),
        source, shared, Priority.IMPORTANT, Category.CHANGE, insight_type,
    )


def _categorical_trend_insight(label, trend, source, shared, insight_type):
    return _insight(
        f"{label} remained stable." if trend.stable else f"{label} was modified.",
        f"The supplied {label.lower()} history remains visible.",
        (("Observed values", *trend.observed_values), ("Classification", trend.classification)),
        source, shared, Priority.IMPORTANT, Category.TREND, insight_type,
    )


def _collection_change_insights(label, transition, source, shared, insight_type):
    values = []
    if transition.added:
        values.append(_insight(
            f"{label} became present.", f"One or more supplied {label.lower()} identities were added.",
            (("Added", *transition.added),), source, shared,
            Priority.INFORMATIONAL, Category.CHANGE, insight_type,
        ))
    if transition.removed:
        values.append(_insight(
            f"{label} became absent.", f"One or more supplied {label.lower()} identities were removed.",
            (("Removed", *transition.removed),), source, shared,
            Priority.INFORMATIONAL, Category.CHANGE, insight_type,
        ))
    return tuple(values)


def _presence_insights(label, trend, source, shared, insight_type):
    if not trend.items:
        return ()
    return tuple(
        _insight(
            f"{label} presence was observed.",
            f"The supplied {label.lower()} presence history remains visible.",
            (("Identity", value.identity), ("Occurrences", value.occurrence_count), ("Transitions", value.transition_count), ("Latest present", value.latest_present)),
            source, shared, Priority.INFORMATIONAL, Category.TREND, insight_type,
        )
        for value in trend.items
    )


def _insight(title, summary, evidence, source, shared, priority, category, insight_type):
    reasons, diagnostics, provenance = shared
    return IntelligenceInsight(
        title, summary,
        tuple(IntelligenceInsightEvidence(label, tuple(values)) for label, *values in evidence),
        source, tuple(reasons), tuple(diagnostics), provenance, priority, category, insight_type,
    )


def _available(category, insights):
    return IntelligenceInsightCollection(State.AVAILABLE, category, tuple(insights), "Insights available.")


def _label(value):
    return value.replace("_", " ").capitalize()


__all__ = ["ChangeInsightGenerator", "SnapshotInsightGenerator", "TrendInsightGenerator"]
