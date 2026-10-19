"""Read-only Artist membership inspection of an exact retained Portfolio."""

from dataclasses import dataclass

from dip.app.current_collection_portfolio import CurrentCollectionPortfolio
from dip.app.current_release_metadata import CurrentReleaseMetadata, CurrentReleaseMetadataRepository
from dip.portfolio_intelligence.portfolio_distribution import (
    PortfolioCategoryDistributionEntry, PortfolioDistributionDimension,
    validate_portfolio_distribution_output,
)

LABEL_FAILURE = "Current catalogue labels could not be loaded. Retained membership and totals are unchanged."


@dataclass(frozen=True, slots=True)
class ArtistInspectionMember:
    release_id: int
    copies_at_calculation: int
    current_metadata: CurrentReleaseMetadata | None

    def __post_init__(self):
        if type(self.release_id) is not int or self.release_id <= 0:
            raise ValueError("Member release ID must be a positive integer.")
        if type(self.copies_at_calculation) is not int or self.copies_at_calculation <= 0:
            raise ValueError("Retained copies must be a positive integer.")
        if self.current_metadata is not None and (
            type(self.current_metadata) is not CurrentReleaseMetadata
            or self.current_metadata.release_id != self.release_id
        ):
            raise ValueError("Current labels must match the retained member identity.")


@dataclass(frozen=True, slots=True)
class ArtistInspection:
    source: CurrentCollectionPortfolio
    category: PortfolioCategoryDistributionEntry
    members: tuple[ArtistInspectionMember, ...]
    label_error: str = ""

    def __post_init__(self):
        if type(self.source) is not CurrentCollectionPortfolio:
            raise TypeError("Inspection requires an exact retained Portfolio.")
        artist = next(value for value in self.source.distribution.output.dimensions
                      if value.dimension is PortfolioDistributionDimension.ARTIST)
        if not any(value is self.category for value in artist.entries):
            raise ValueError("Category must belong to this retained Artist result.")
        if type(self.members) is not tuple or any(type(value) is not ArtistInspectionMember for value in self.members):
            raise TypeError("Members must be an immutable typed tuple.")
        if tuple(value.release_id for value in self.members) != self.category.release_ids:
            raise ValueError("Inspection must preserve complete ordered membership.")
        quantities = {value.release_id: value.quantity for value in self.source.distribution.output.releases}
        if any(value.copies_at_calculation != quantities[value.release_id] for value in self.members):
            raise ValueError("Inspection quantities must match the retained source.")
        if self.label_error not in ("", LABEL_FAILURE):
            raise ValueError("Inspection requires fixed safe error copy.")
        if self.label_error and any(value.current_metadata is not None for value in self.members):
            raise ValueError("A failed lookup must not publish partial labels.")


class PortfolioArtistInspectionService:
    def __init__(self, metadata: CurrentReleaseMetadataRepository):
        self._metadata = metadata

    def inspect(self, source: CurrentCollectionPortfolio, category_id: str) -> ArtistInspection:
        if type(source) is not CurrentCollectionPortfolio:
            raise TypeError("source must be a retained Current Collection Portfolio.")
        if type(category_id) is not str or not category_id:
            raise ValueError("category_id must identify a retained Artist category.")
        output = source.distribution.output
        validate_portfolio_distribution_output(output)
        artist = next(value for value in output.dimensions if value.dimension is PortfolioDistributionDimension.ARTIST)
        category = next((value for value in artist.entries if value.category_id == category_id), None)
        if category is None:
            raise ValueError("Artist category is not present in the retained Portfolio.")
        details = {value.release_id: value for value in output.releases}
        labels = {}
        error = ""
        try:
            returned = self._metadata.metadata_for_release_ids(category.release_ids)
            if type(returned) is not tuple:
                raise TypeError("Metadata must be an immutable tuple.")
            for value in returned:
                if type(value) is not CurrentReleaseMetadata or value.release_id not in category.release_ids or value.release_id in labels:
                    raise ValueError("Metadata contains an invalid identity.")
                labels[value.release_id] = value
            if tuple(labels) != tuple(sorted(labels)):
                raise ValueError("Metadata is not in release order.")
        except Exception:
            labels = {}
            error = LABEL_FAILURE
        return ArtistInspection(source, category, tuple(
            ArtistInspectionMember(value, details[value].quantity, labels.get(value))
            for value in category.release_ids
        ), error)
