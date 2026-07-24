"""Neutral rendering of already-produced Intelligence Trend Analysis."""

from dataclasses import dataclass

from dip.experience.intelligence_trend_analysis import IntelligenceTrendAnalysisViewModel


@dataclass(frozen=True)
class DesktopIntelligenceTrendAnalysisSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopIntelligenceTrendAnalysisView:
    title: str
    state: object
    headline: str
    summary: str
    sections: tuple[DesktopIntelligenceTrendAnalysisSection, ...] = ()


class DesktopIntelligenceTrendAnalysisRenderer:
    def render(self, detail):
        if type(detail) is not IntelligenceTrendAnalysisViewModel:
            raise TypeError("detail must be IntelligenceTrendAnalysisViewModel.")
        if detail.output is None:
            return DesktopIntelligenceTrendAnalysisView(detail.title, detail.state, _label(detail.state.value), detail.summary_text)
        output = detail.output
        summary = output.summary
        sections = (
            DesktopIntelligenceTrendAnalysisSection(
                "Observed sequence",
                "\n".join((
                    f"Compared module: {summary.compared_module_id or 'Unavailable'}",
                    f"Input comparisons: {summary.comparison_count}",
                    f"Represented observations: {summary.observation_count}",
                    f"First snapshot: {output.provenance.first_snapshot_identity}",
                    f"Latest snapshot: {output.provenance.latest_snapshot_identity}",
                    f"Overall pattern: {_label(summary.overall_pattern.value)}",
                    f"Trend evidence: {_label(summary.evidence_coverage.value)}",
                )),
            ),
            DesktopIntelligenceTrendAnalysisSection(
                "Assessment and evidence history",
                "\n".join((
                    f"Assessment: {_values(output.assessment_trend.observed_values)}; {_label(output.assessment_trend.classification.value)}",
                    f"Assessment transitions: {_values(output.assessment_trend.transition_states)}",
                    f"Evidence: {_values(output.evidence_trend.observed_values)}; {_label(output.evidence_trend.classification.value)}",
                    f"Evidence transitions: {_values(output.evidence_trend.transition_states)}",
                )),
            ),
            DesktopIntelligenceTrendAnalysisSection(
                "Numeric metric trends",
                "\n\n".join(_metric(value) for value in output.numeric_metric_trends) or "No usable numeric trends.",
            ),
            DesktopIntelligenceTrendAnalysisSection(
                "Reasons, diagnostics, and dimensions",
                "\n".join((
                    f"Reasons added: {_values(output.reason_trend.added_values)}",
                    f"Reasons removed: {_values(output.reason_trend.removed_values)}",
                    f"Diagnostics added: {_values(output.diagnostic_trend.added_values)}",
                    f"Diagnostics removed: {_values(output.diagnostic_trend.removed_values)}",
                    f"Dimensions added: {_values(output.dimension_trend.added_dimensions)}",
                    f"Dimensions removed: {_values(output.dimension_trend.removed_dimensions)}",
                    f"Became usable: {_values(output.dimension_trend.became_usable)}",
                    f"Became unusable: {_values(output.dimension_trend.became_unusable)}",
                )),
            ),
            DesktopIntelligenceTrendAnalysisSection(
                "Rules and provenance",
                "\n".join((
                    f"Trend rule set: {output.rule_set_version}",
                    f"Minimum comparisons: {output.rule_configuration.minimum_comparison_count}",
                    f"Strict consistent direction: {output.rule_configuration.strict_consistent_direction}",
                    f"Snapshot chain: {_values(output.provenance.ordered_snapshot_chain)}",
                    *(f"Reason: {_label(value.value)}" for value in output.reason_codes),
                    *(f"{value.code.value}: {value.message}" for value in output.diagnostics),
                    *detail.diagnostics,
                )),
            ),
        )
        return DesktopIntelligenceTrendAnalysisView(
            detail.title, detail.state, f"Historical pattern: {_label(summary.overall_pattern.value)}",
            detail.summary_text, sections,
        )


class DesktopIntelligenceTrendAnalysisController:
    def __init__(self, presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopIntelligenceTrendAnalysisRenderer()

    def open(self, result):
        return self._renderer.render(self._presentation.trend_analysis_for_result(result))


def _metric(value):
    return "\n".join((
        f"{_label(value.metric_id)}: {value.first_value} → {value.latest_value}",
        f"Net delta: {value.net_delta}; range: {value.minimum_value} to {value.maximum_value}",
        f"Increased: {value.increase_count}; decreased: {value.decrease_count}; unchanged: {value.unchanged_count}",
        f"Direction changes: {value.direction_change_count}; runs increased/decreased/unchanged: {value.longest_increasing_run}/{value.longest_decreasing_run}/{value.longest_unchanged_run}",
        f"Classification: {_label(value.classification.value)}",
    ))


def _values(values):
    return ", ".join(_label(value.value) if hasattr(value, "value") else str(value) for value in values) or "none"


def _label(value):
    return value.replace("_", " ").title()


__all__ = ["DesktopIntelligenceTrendAnalysisController", "DesktopIntelligenceTrendAnalysisRenderer"]
