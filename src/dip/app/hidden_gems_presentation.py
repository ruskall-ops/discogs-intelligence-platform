"""Application coordination for the Hidden Gems detail experience."""

from __future__ import annotations

from typing import Protocol

from dip.experience.dashboard import (
    DashboardHiddenGemsViewModel,
    DashboardHomepageConsistencyError,
    DashboardHomepageViewModel,
    DashboardSectionId,
)
from dip.experience.hidden_gems import HiddenGemsDetailViewModel


class _HiddenGemsDetailBuilder(Protocol):
    def build(
        self,
        section: DashboardHiddenGemsViewModel,
    ) -> HiddenGemsDetailViewModel: ...


class HiddenGemsPresentationService:
    """Transform the homepage's Hidden Gems section into detail."""

    def __init__(self, builder: _HiddenGemsDetailBuilder) -> None:
        self._builder = builder

    def detail_for_homepage(
        self,
        homepage: DashboardHomepageViewModel,
    ) -> HiddenGemsDetailViewModel:
        """Build detail from the same latest result displayed on the homepage."""

        if type(homepage) is not DashboardHomepageViewModel:
            raise TypeError("homepage must be a DashboardHomepageViewModel.")
        section = homepage.section_for(DashboardSectionId.HIDDEN_GEMS)
        if type(section) is not DashboardHiddenGemsViewModel:
            raise DashboardHomepageConsistencyError(
                "The homepage does not contain a Hidden Gems section."
            )
        return self.build_detail(section)

    def build_detail(
        self,
        section: DashboardHiddenGemsViewModel,
    ) -> HiddenGemsDetailViewModel:
        """Transform an already selected Hidden Gems homepage section."""

        return self._builder.build(section)


__all__ = ["HiddenGemsPresentationService"]
