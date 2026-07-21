"""Application bootstrap and use-case orchestration."""

from .intelligence_history import (
    HistoricalIntelligenceExecution,
    HistoricalModuleResult,
    IntelligenceHistoryConsistencyError,
    IntelligenceHistoryQueryService,
)


def main() -> None:
    """Start the desktop application."""

    from dip.experience.desktop.app import App

    App().mainloop()


__all__ = [
    "HistoricalIntelligenceExecution",
    "HistoricalModuleResult",
    "IntelligenceHistoryConsistencyError",
    "IntelligenceHistoryQueryService",
    "main",
]
