"""Thin presentation boundary for already-produced Change Analysis."""


class IntelligenceChangeAnalysisPresentationService:
    def __init__(self, builder):
        self._builder = builder

    def change_analysis_for_result(self, result):
        return self._builder.build(result)


__all__ = ["IntelligenceChangeAnalysisPresentationService"]
