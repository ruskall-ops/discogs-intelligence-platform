"""Explicit deterministic Insight generation over supplied ViewModels."""


class IntelligenceInsightsPresentationService:
    def __init__(self, snapshot_generator, change_generator, trend_generator):
        self._snapshot = snapshot_generator
        self._change = change_generator
        self._trend = trend_generator

    def snapshot_insights(self, view_model):
        return self._snapshot.generate(view_model)

    def change_insights(self, view_model):
        return self._change.generate(view_model)

    def trend_insights(self, view_model):
        return self._trend.generate(view_model)


__all__ = ["IntelligenceInsightsPresentationService"]
