"""Thin presentation boundary for already-produced Trend Analysis."""


class IntelligenceTrendAnalysisPresentationService:
    def __init__(self, builder):
        self._builder = builder

    def trend_analysis_for_result(self, result):
        return self._builder.build(result)


__all__ = ["IntelligenceTrendAnalysisPresentationService"]
