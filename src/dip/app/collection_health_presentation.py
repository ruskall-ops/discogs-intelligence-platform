"""Application coordination for the Collection Health detail experience."""

from __future__ import annotations

from typing import Protocol

from dip.experience.collection_health import CollectionHealthDetailViewModel
from dip.experience.dashboard import (
    DashboardCollectionHealthViewModel,
    DashboardHomepageConsistencyError,
    DashboardHomepageViewModel,
    DashboardSectionId,
)


class _CollectionHealthDetailBuilder(Protocol):
    def build(
        self,
        section: DashboardCollectionHealthViewModel,
    ) -> CollectionHealthDetailViewModel: ...


class CollectionHealthPresentationService:
    """Transform the homepage's Collection Health section into detail."""

    def __init__(self, builder: _CollectionHealthDetailBuilder) -> None:
        self._builder = builder

    def detail_for_homepage(
        self,
        homepage: DashboardHomepageViewModel,
    ) -> CollectionHealthDetailViewModel:
        """Build detail from the same latest result displayed on the homepage."""

        if type(homepage) is not DashboardHomepageViewModel:
            raise TypeError("homepage must be a DashboardHomepageViewModel.")
        section = homepage.section_for(DashboardSectionId.COLLECTION_HEALTH)
        if type(section) is not DashboardCollectionHealthViewModel:
            raise DashboardHomepageConsistencyError(
                "The homepage does not contain a Collection Health section."
            )
        return self.build_detail(section)

    def build_detail(
        self,
        section: DashboardCollectionHealthViewModel,
    ) -> CollectionHealthDetailViewModel:
        """Transform an already selected Collection Health homepage section."""

        return self._builder.build(section)


__all__ = ["CollectionHealthPresentationService"]
