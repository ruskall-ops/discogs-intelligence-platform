"""Application orchestration for comparison presentation ViewModels."""

from __future__ import annotations

from typing import Protocol

from dip.comparison import ExecutionComparison
from dip.experience.comparison import ExecutionComparisonViewModel


class _ComparisonQueries(Protocol):
    def compare_latest(self) -> ExecutionComparison: ...

    def compare_by_run_ids(
        self,
        current_run_id: int,
        previous_run_id: int,
    ) -> ExecutionComparison: ...


class _ComparisonViewModelBuilder(Protocol):
    def build(
        self,
        comparison: ExecutionComparison,
    ) -> ExecutionComparisonViewModel: ...


class ComparisonPresentationService:
    """Compose comparison application results with presentation transformation."""

    def __init__(
        self,
        comparison_service: _ComparisonQueries,
        view_model_builder: _ComparisonViewModelBuilder,
    ) -> None:
        self._comparison_service = comparison_service
        self._view_model_builder = view_model_builder

    def latest_view_model(self) -> ExecutionComparisonViewModel:
        """Build a ViewModel for the latest two historical executions."""

        return self.build_view_model(self._comparison_service.compare_latest())

    def view_model_for_runs(
        self,
        current_run_id: int,
        previous_run_id: int,
    ) -> ExecutionComparisonViewModel:
        """Build a ViewModel for two requested historical run identifiers."""

        comparison = self._comparison_service.compare_by_run_ids(
            current_run_id,
            previous_run_id,
        )
        return self.build_view_model(comparison)

    def build_view_model(
        self,
        comparison: ExecutionComparison,
    ) -> ExecutionComparisonViewModel:
        """Transform an existing structured comparison without querying history."""

        return self._view_model_builder.build(comparison)


__all__ = ["ComparisonPresentationService"]
