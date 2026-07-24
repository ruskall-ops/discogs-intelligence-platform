"""Neutral desktop rendering for already-produced Historical Intelligence."""

from dataclasses import dataclass

from dip.experience.intelligence_change_analysis import IntelligenceChangeAnalysisViewModel


@dataclass(frozen=True)
class DesktopIntelligenceChangeAnalysisSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopIntelligenceChangeAnalysisView:
    title: str
    state: object
    headline: str
    summary: str
    sections: tuple[DesktopIntelligenceChangeAnalysisSection, ...] = ()


class DesktopIntelligenceChangeAnalysisRenderer:
    def render(self, detail):
        if type(detail) is not IntelligenceChangeAnalysisViewModel:
            raise TypeError("detail must be IntelligenceChangeAnalysisViewModel.")
        if detail.output is None:
            return DesktopIntelligenceChangeAnalysisView(
                detail.title, detail.state, _label(detail.state.value), detail.summary_text,
            )
        output = detail.output
        sections = (
            DesktopIntelligenceChangeAnalysisSection(
                "Assessment and evidence",
                "\n".join((
                    f"Compared module: {output.summary.compared_module_id or 'Unavailable'}",
                    f"Assessment: {_transition(output.assessment)}",
                    f"Evidence: {_transition(output.evidence)}",
                    f"Overall state: {_label(output.summary.comparison_state.value)}",
                )),
            ),
            DesktopIntelligenceChangeAnalysisSection(
                "Metric changes",
                "\n".join(
                    f"{_label(value.metric_id)}: {value.previous} → {value.current}; delta {value.delta}; {_label(value.comparison_state.value)}"
                    for value in output.metrics
                ) or "No comparable metrics.",
            ),
            DesktopIntelligenceChangeAnalysisSection(
                "Versions and source collections",
                "\n".join((
                    f"Module version: {_transition(output.module_version)}",
                    f"Source rule set: {_transition(output.source_rule_set)}",
                    f"Supported dimensions: {_collection(output.supported_dimensions)}",
                    f"Unusable dimensions: {_collection(output.unusable_dimensions)}",
                    f"Reasons: {_collection(output.reasons)}",
                    f"Source diagnostics: {_collection(output.diagnostics)}",
                )),
            ),
            DesktopIntelligenceChangeAnalysisSection(
                "Provenance",
                "\n".join((
                    f"Previous module: {output.provenance.previous_module_id} {output.provenance.previous_module_version}",
                    f"Current module: {output.provenance.current_module_id} {output.provenance.current_module_version}",
                    f"Previous snapshot: {output.provenance.previous_collection_snapshot_id}",
                    f"Current snapshot: {output.provenance.current_collection_snapshot_id}",
                    f"Comparison rule set: {output.provenance.comparison_rule_set_version}",
                    f"Supported module: {output.provenance.supported_module_id}",
                )),
            ),
            DesktopIntelligenceChangeAnalysisSection(
                "Reasons and diagnostics",
                "\n".join((
                    *(f"Reason: {_label(value.value)}" for value in output.reason_codes),
                    *(f"{value.code.value}: {value.message}" for value in output.output_diagnostics),
                    *detail.diagnostics,
                )) or "No diagnostics.",
            ),
        )
        return DesktopIntelligenceChangeAnalysisView(
            detail.title, detail.state,
            f"Change Analysis: {_label(output.summary.comparison_state.value)}",
            detail.summary_text, sections,
        )


class DesktopIntelligenceChangeAnalysisController:
    def __init__(self, presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopIntelligenceChangeAnalysisRenderer()

    def open(self, result):
        return self._renderer.render(self._presentation.change_analysis_for_result(result))


def _transition(value):
    return f"{_value(value.previous)} → {_value(value.current)}; {_label(value.comparison_state.value)}"


def _collection(value):
    return f"{_values(value.previous)} → {_values(value.current)}; {_label(value.comparison_state.value)}"


def _values(values):
    return ", ".join(_value(value) for value in values) or "none"


def _value(value):
    return "Unavailable" if value is None else _label(value.value) if hasattr(value, "value") else str(value)


def _label(value):
    return value.replace("_", " ").title()


__all__ = [
    "DesktopIntelligenceChangeAnalysisController",
    "DesktopIntelligenceChangeAnalysisRenderer",
    "DesktopIntelligenceChangeAnalysisView",
]
