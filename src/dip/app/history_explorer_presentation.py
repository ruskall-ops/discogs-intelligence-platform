"""Presentation-state boundary for already-produced historical ViewModels."""


class HistoryExplorerPresentationService:
    def __init__(self, builder):
        self._builder = builder

    def explorer(self, observations=(), changes=(), trends=(), **selection):
        return self._builder.build(observations, changes, trends, **selection)

    def select(self, state, **selection):
        return self._builder.select(state, **selection)


__all__ = ["HistoryExplorerPresentationService"]
