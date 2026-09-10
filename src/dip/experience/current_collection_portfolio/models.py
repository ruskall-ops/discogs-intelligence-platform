"""Closed immutable models for Current Collection Portfolio presentation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from enum import Enum
from fractions import Fraction


class PortfolioDestination(str, Enum):
    DISTRIBUTION = "distribution"
    CONCENTRATION = "concentration"


class PortfolioPresentationAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


_DESTINATION_TITLES = {
    PortfolioDestination.DISTRIBUTION: "Distribution",
    PortfolioDestination.CONCENTRATION: "Concentration",
}
_DIMENSION_TITLES = {
    "artist": "Artist",
    "label": "Label",
    "format": "Format",
    "release_year": "Release year",
    "decade": "Decade",
}
_DIMENSION_ORDER = tuple(_DIMENSION_TITLES)
_ANALYSIS_COPY = {
    "complete": "Complete evidence",
    "partial": "Partial evidence",
    "insufficient_data": "Insufficient evidence",
}
_CONCENTRATION_STATE_COPY = {
    "dispersed": "Mathematically dispersed",
    "moderate": "Mathematically moderate",
    "concentrated": "Mathematically concentrated",
    "highly_concentrated": "Mathematically highly concentrated",
    "insufficient": "Insufficient represented memberships",
}
_SOURCE_COPY = "Calculated from current ownership and catalogue metadata"
_ROUNDING_COPY = "Percentages are rounded independently to two decimal places and may not total 100%."
_MISSING_COPY = "Missing metadata is excluded from categories; it is not relabelled Unknown."
_DENOMINATOR_COPY = (
    "Concentration uses represented memberships only; holdings missing this dimension's metadata are excluded. "
    "Full collection coverage is shown alongside it."
)
_INTERPRETATION_COPY = (
    "Concentration describes mathematical clustering only. It is not risk, diversification advice, valuation, "
    "opportunity scoring, a recommendation, or an aggregate Portfolio score."
)
_FAILURE_COPY = "Portfolio could not be calculated. Existing saved data has been preserved."


def format_percentage(value: Decimal) -> str:
    if type(value) is not Decimal:
        raise TypeError("value must be a Decimal.")
    if not value.is_finite():
        return "Unavailable"
    try:
        rounded = (value * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    except InvalidOperation:
        return "Unavailable"
    return f"{rounded:.2f}%"


@dataclass(frozen=True, slots=True)
class PortfolioNavigationItem:
    destination: PortfolioDestination

    def __post_init__(self) -> None:
        _exact(self.destination, PortfolioDestination, "destination")

    @property
    def title(self) -> str:
        return _DESTINATION_TITLES[self.destination]


@dataclass(frozen=True, slots=True)
class PresentedRatio:
    numerator: int
    denominator: int
    domain_ratio: Decimal

    def __post_init__(self) -> None:
        _non_negative(self.numerator, "numerator")
        _non_negative(self.denominator, "denominator")
        _exact(self.domain_ratio, Decimal, "domain_ratio")
        if self.denominator == 0:
            if self.numerator != 0 or self.domain_ratio != Decimal("0"):
                raise ValueError("A zero-denominator ratio must be the factual zero/zero outcome.")
        elif not _represents_ratio(self.domain_ratio, self.numerator, self.denominator):
            raise ValueError("domain_ratio contradicts numerator and denominator.")

    @property
    def percentage(self) -> str:
        return format_percentage(self.domain_ratio)


@dataclass(frozen=True, slots=True)
class PresentedDecimal:
    domain_value: Decimal | None
    show_percentage: bool = False

    def __post_init__(self) -> None:
        if self.domain_value is not None:
            _exact(self.domain_value, Decimal, "domain_value")
        if type(self.show_percentage) is not bool:
            raise TypeError("show_percentage must be a bool.")

    @property
    def value_text(self) -> str:
        if self.domain_value is None or not self.domain_value.is_finite():
            return "Unavailable"
        return format(self.domain_value, "f")

    @property
    def percentage(self) -> str | None:
        return format_percentage(self.domain_value) if self.show_percentage and self.domain_value is not None else None


@dataclass(frozen=True, slots=True)
class DistributionCategoryPresentation:
    category_id: str
    label: str
    release_share: PresentedRatio
    copy_share: PresentedRatio
    release_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        _text(self.category_id, "category_id")
        _text(self.label, "label")
        _exact(self.release_share, PresentedRatio, "release_share")
        _exact(self.copy_share, PresentedRatio, "copy_share")
        _positive_ids(self.release_ids, "release_ids")
        if self.release_ids != tuple(sorted(self.release_ids)) or len(set(self.release_ids)) != len(self.release_ids):
            raise ValueError("release_ids must be unique and ascending.")
        if self.release_share.numerator != len(self.release_ids):
            raise ValueError("release_share numerator contradicts release_ids.")


@dataclass(frozen=True, slots=True)
class DistributionDimensionPresentation:
    dimension_id: str
    represented_category_count: int
    releases_with_metadata: int
    copies_with_metadata: int
    release_coverage: PresentedRatio
    copy_coverage: PresentedRatio
    releases_missing_metadata: int
    copies_missing_metadata: int
    missing_release_ids: tuple[int, ...]
    categories: tuple[DistributionCategoryPresentation, ...]

    def __post_init__(self) -> None:
        if self.dimension_id not in _DIMENSION_TITLES:
            raise ValueError("dimension_id is unsupported.")
        for name in (
            "represented_category_count",
            "releases_with_metadata",
            "copies_with_metadata",
        ):
            _non_negative(getattr(self, name), name)
        _exact(self.release_coverage, PresentedRatio, "release_coverage")
        _exact(self.copy_coverage, PresentedRatio, "copy_coverage")
        _non_negative(self.releases_missing_metadata, "releases_missing_metadata")
        _non_negative(self.copies_missing_metadata, "copies_missing_metadata")
        _positive_ids(self.missing_release_ids, "missing_release_ids")
        _typed_tuple(self.categories, DistributionCategoryPresentation, "categories")
        if self.releases_with_metadata + self.releases_missing_metadata != self.release_coverage.denominator:
            raise ValueError("Release metadata counts contradict the full denominator.")
        if self.copies_with_metadata + self.copies_missing_metadata != self.copy_coverage.denominator:
            raise ValueError("Copy metadata counts contradict the full denominator.")
        if self.release_coverage.numerator != self.releases_with_metadata or self.copy_coverage.numerator != self.copies_with_metadata:
            raise ValueError("Metadata coverage ratios contradict their factual counts.")
        if self.represented_category_count != len(self.categories):
            raise ValueError("represented_category_count contradicts category rows.")
        if self.missing_release_ids != tuple(sorted(self.missing_release_ids)) or len(set(self.missing_release_ids)) != len(self.missing_release_ids):
            raise ValueError("missing_release_ids must be unique and ascending.")
        if len(self.missing_release_ids) != self.releases_missing_metadata:
            raise ValueError("missing_release_ids contradict the missing release count.")
        identities = tuple((row.category_id, row.label) for row in self.categories)
        if len(set(identities)) != len(identities):
            raise ValueError("Category identities must be unique.")
        for category in self.categories:
            if category.release_share.denominator != self.release_coverage.denominator or category.copy_share.denominator != self.copy_coverage.denominator:
                raise ValueError("Category shares must use the dimension's full denominators.")

    @property
    def title(self) -> str:
        return _DIMENSION_TITLES[self.dimension_id]

    @property
    def missing_metadata_copy(self) -> str:
        return _MISSING_COPY

    @property
    def largest_release_categories(self) -> tuple[DistributionCategoryPresentation, ...]:
        if not self.categories:
            return ()
        maximum = max(row.release_share.numerator for row in self.categories)
        return tuple(row for row in self.categories if row.release_share.numerator == maximum)

    @property
    def largest_copy_categories(self) -> tuple[DistributionCategoryPresentation, ...]:
        if not self.categories:
            return ()
        maximum = max(row.copy_share.numerator for row in self.categories)
        return tuple(row for row in self.categories if row.copy_share.numerator == maximum)

    @property
    def largest_category_id(self) -> str | None:
        return None if not self._canonical_largest_categories else self._canonical_largest_categories[0].category_id

    @property
    def largest_category_label(self) -> str | None:
        return None if not self._canonical_largest_categories else self._canonical_largest_categories[0].label

    @property
    def largest_release_share(self) -> PresentedRatio | None:
        return None if not self.largest_release_categories else self.largest_release_categories[0].release_share

    @property
    def largest_copy_share(self) -> PresentedRatio | None:
        return None if not self.largest_copy_categories else self.largest_copy_categories[0].copy_share

    @property
    def tied_largest_category_count(self) -> int:
        return len(self._canonical_largest_categories)

    @property
    def _canonical_largest_categories(self) -> tuple[DistributionCategoryPresentation, ...]:
        if not self.categories:
            return ()
        release_largest = self.largest_release_categories
        maximum_copy = max(row.copy_share.numerator for row in release_largest)
        return tuple(row for row in release_largest if row.copy_share.numerator == maximum_copy)


@dataclass(frozen=True, slots=True)
class DistributionPresentation:
    state: str
    unique_owned_releases: int
    owned_copies: int
    duplicate_copies: int
    dimensions: tuple[DistributionDimensionPresentation, ...]
    module_id: str
    module_version: str
    rule_set_version: str
    evidence_coverage: str
    source_query_id: str
    ownership_data_version: str
    collection_snapshot_id: int | None

    def __post_init__(self) -> None:
        for name in ("state", "module_id", "module_version", "rule_set_version", "evidence_coverage", "source_query_id", "ownership_data_version"):
            _text(getattr(self, name), name)
        if self.collection_snapshot_id is not None:
            _positive(self.collection_snapshot_id, "collection_snapshot_id")
        for name in ("unique_owned_releases", "owned_copies", "duplicate_copies"):
            _non_negative(getattr(self, name), name)
        if self.state not in ("complete", "partial", "insufficient_data"):
            raise ValueError("state is unsupported.")
        if self.evidence_coverage not in ("complete", "partial", "limited", "insufficient"):
            raise ValueError("evidence_coverage is unsupported.")
        if (self.state == "complete" and self.evidence_coverage != "complete") or (self.state == "partial" and self.evidence_coverage == "insufficient") or (self.state == "insufficient_data" and self.evidence_coverage != "insufficient"):
            raise ValueError("Distribution state contradicts evidence coverage.")
        if self.module_id != "portfolio_distribution" or self.module_version != "1.0" or self.rule_set_version != "1.0":
            raise ValueError("Distribution identity is unsupported.")
        _typed_tuple(self.dimensions, DistributionDimensionPresentation, "dimensions")
        if tuple(item.dimension_id for item in self.dimensions) != _DIMENSION_ORDER:
            raise ValueError("Distribution dimensions must use the fixed version-1 order.")

    @property
    def state_copy(self) -> str:
        return _ANALYSIS_COPY[self.state]

    @property
    def source_copy(self) -> str:
        return _SOURCE_COPY

    @property
    def rounding_copy(self) -> str:
        return _ROUNDING_COPY

    @property
    def collection_snapshot(self) -> str:
        return "Not supplied" if self.collection_snapshot_id is None else str(self.collection_snapshot_id)


@dataclass(frozen=True, slots=True)
class ConcentrationContributionPresentation:
    category_id: str
    label: str
    membership_count: int
    release_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        _text(self.category_id, "category_id")
        _text(self.label, "label")
        _non_negative(self.membership_count, "membership_count")
        _positive_ids(self.release_ids, "release_ids")


@dataclass(frozen=True, slots=True)
class FirstCategoriesPresentation:
    requested_count: int
    included_count: int
    membership_share: PresentedRatio
    contributors: tuple[ConcentrationContributionPresentation, ...]

    def __post_init__(self) -> None:
        if type(self.requested_count) is not int or self.requested_count not in (3, 5):
            raise ValueError("requested_count must be 3 or 5.")
        _non_negative(self.included_count, "included_count")
        _exact(self.membership_share, PresentedRatio, "membership_share")
        _typed_tuple(self.contributors, ConcentrationContributionPresentation, "contributors")
        if self.included_count != len(self.contributors) or self.included_count > self.requested_count:
            raise ValueError("included_count contradicts requested count or contributors.")
        if self.membership_share.numerator != sum(item.membership_count for item in self.contributors):
            raise ValueError("First-N numerator contradicts contributor memberships.")

    @property
    def title(self) -> str:
        return f"First {self.requested_count} categories in Distribution order"


@dataclass(frozen=True, slots=True)
class ConcentrationBasisPresentation:
    basis_id: str
    membership_total: int
    represented_category_count: int
    contributors: tuple[ConcentrationContributionPresentation, ...]
    largest_share: PresentedRatio | None
    largest_categories: tuple[ConcentrationContributionPresentation, ...]
    first_three: FirstCategoriesPresentation | None
    first_five: FirstCategoriesPresentation | None
    hhi: PresentedDecimal
    normalized_hhi: PresentedDecimal
    effective_category_count: PresentedDecimal
    state: str

    def __post_init__(self) -> None:
        if self.basis_id not in ("release_membership", "copy_membership"):
            raise ValueError("basis_id is unsupported.")
        _non_negative(self.membership_total, "membership_total")
        _non_negative(self.represented_category_count, "represented_category_count")
        _typed_tuple(self.contributors, ConcentrationContributionPresentation, "contributors")
        identities = tuple((item.category_id, item.label) for item in self.contributors)
        if len(set(identities)) != len(identities) or self.represented_category_count != len(self.contributors):
            raise ValueError("Contributors must be unique and match represented_category_count.")
        if self.membership_total != sum(item.membership_count for item in self.contributors):
            raise ValueError("Contributors contradict represented-membership total.")
        if self.largest_share is not None:
            _exact(self.largest_share, PresentedRatio, "largest_share")
        _typed_tuple(self.largest_categories, ConcentrationContributionPresentation, "largest_categories")
        if self.first_three is not None:
            _exact(self.first_three, FirstCategoriesPresentation, "first_three")
        if self.first_five is not None:
            _exact(self.first_five, FirstCategoriesPresentation, "first_five")
        for value, name in ((self.hhi, "hhi"), (self.normalized_hhi, "normalized_hhi"), (self.effective_category_count, "effective_category_count")):
            _exact(value, PresentedDecimal, name)
        _text(self.state, "state")
        if self.state not in ("dispersed", "moderate", "concentrated", "highly_concentrated", "insufficient"):
            raise ValueError("concentration state is unsupported.")
        for value, requested, name in ((self.first_three, 3, "first_three"), (self.first_five, 5, "first_five")):
            if value is not None:
                if value.requested_count != requested or value.membership_share.denominator != self.membership_total:
                    raise ValueError(f"{name} contradicts its position or represented-membership denominator.")
        unavailable = self.membership_total == 0
        if unavailable:
            if self.largest_share is not None or self.largest_categories or self.first_three is not None or self.first_five is not None or any(item.domain_value is not None for item in (self.hhi, self.normalized_hhi, self.effective_category_count)) or self.state != "insufficient":
                raise ValueError("No-membership concentration must remain unavailable.")
        elif self.largest_share is None or self.largest_share.denominator != self.membership_total or not self.largest_categories:
            raise ValueError("Available concentration requires authoritative largest-category facts.")
        elif any(item.membership_count != self.largest_share.numerator for item in self.largest_categories):
            raise ValueError("Largest-category contributors contradict the largest share.")
        if not unavailable:
            maximum = max(item.membership_count for item in self.contributors)
            expected_largest = tuple(item for item in self.contributors if item.membership_count == maximum)
            if self.largest_categories != expected_largest:
                raise ValueError("largest_categories must be the complete ordered maximum set.")
            for first in (self.first_three, self.first_five):
                if first is not None and first.contributors != self.contributors[: first.included_count]:
                    raise ValueError("First-N contributors must retain authoritative order.")

    @property
    def title(self) -> str:
        return "Release membership" if self.basis_id == "release_membership" else "Copy membership"

    @property
    def denominator_label(self) -> str:
        return "represented releases" if self.basis_id == "release_membership" else "represented copies"

    @property
    def state_copy(self) -> str:
        return _CONCENTRATION_STATE_COPY[self.state]


@dataclass(frozen=True, slots=True)
class ConcentrationDifferencePresentation:
    largest_category_share_delta: PresentedDecimal
    first_three_share_delta: PresentedDecimal
    first_five_share_delta: PresentedDecimal
    hhi_delta: PresentedDecimal
    normalized_hhi_delta: PresentedDecimal
    effective_category_count_delta: PresentedDecimal

    def __post_init__(self) -> None:
        for name in (
            "largest_category_share_delta",
            "first_three_share_delta",
            "first_five_share_delta",
            "hhi_delta",
            "normalized_hhi_delta",
            "effective_category_count_delta",
        ):
            _exact(getattr(self, name), PresentedDecimal, name)


@dataclass(frozen=True, slots=True)
class ConcentrationDimensionPresentation:
    dimension_id: str
    represented_category_count: int
    release_coverage: PresentedRatio
    copy_coverage: PresentedRatio
    missing_release_ids: tuple[int, ...]
    release_basis: ConcentrationBasisPresentation
    copy_basis: ConcentrationBasisPresentation
    difference: ConcentrationDifferencePresentation

    def __post_init__(self) -> None:
        if self.dimension_id not in _DIMENSION_TITLES:
            raise ValueError("dimension_id is unsupported.")
        _non_negative(self.represented_category_count, "represented_category_count")
        _exact(self.release_coverage, PresentedRatio, "release_coverage")
        _exact(self.copy_coverage, PresentedRatio, "copy_coverage")
        _positive_ids(self.missing_release_ids, "missing_release_ids")
        _exact(self.release_basis, ConcentrationBasisPresentation, "release_basis")
        _exact(self.copy_basis, ConcentrationBasisPresentation, "copy_basis")
        _exact(self.difference, ConcentrationDifferencePresentation, "difference")
        if self.release_basis.basis_id != "release_membership" or self.copy_basis.basis_id != "copy_membership":
            raise ValueError("Concentration bases are in the wrong positions.")
        if self.release_basis.membership_total != self.release_coverage.numerator or self.copy_basis.membership_total != self.copy_coverage.numerator:
            raise ValueError("Represented memberships contradict full-collection coverage.")
        if self.represented_category_count != self.release_basis.represented_category_count or self.represented_category_count != self.copy_basis.represented_category_count:
            raise ValueError("Represented category counts contradict their bases.")
        if self.missing_release_ids != tuple(sorted(self.missing_release_ids)) or len(set(self.missing_release_ids)) != len(self.missing_release_ids):
            raise ValueError("missing_release_ids must be unique and ascending.")
        if len(self.missing_release_ids) != self.release_coverage.denominator - self.release_coverage.numerator:
            raise ValueError("missing_release_ids contradict release coverage.")

    @property
    def title(self) -> str:
        return _DIMENSION_TITLES[self.dimension_id]

    @property
    def denominator_copy(self) -> str:
        return _DENOMINATOR_COPY


@dataclass(frozen=True, slots=True)
class ConcentrationPresentation:
    state: str
    unique_owned_releases: int
    owned_copies: int
    duplicate_copies: int
    dimensions: tuple[ConcentrationDimensionPresentation, ...]
    unusable_dimensions: tuple[str, ...]
    module_id: str
    module_version: str
    rule_set_version: str
    evidence_coverage: str
    source_evidence_coverage: str
    source_module_id: str
    source_module_version: str
    source_rule_set_version: str
    source_query_id: str
    ownership_data_version: str
    collection_snapshot_id: int | None

    def __post_init__(self) -> None:
        for name in ("state", "module_id", "module_version", "rule_set_version", "evidence_coverage", "source_evidence_coverage", "source_module_id", "source_module_version", "source_rule_set_version", "source_query_id", "ownership_data_version"):
            _text(getattr(self, name), name)
        if self.collection_snapshot_id is not None:
            _positive(self.collection_snapshot_id, "collection_snapshot_id")
        for name in ("unique_owned_releases", "owned_copies", "duplicate_copies"):
            _non_negative(getattr(self, name), name)
        if self.state not in ("complete", "partial", "insufficient_data"):
            raise ValueError("state is unsupported.")
        if self.evidence_coverage not in ("complete", "partial", "limited", "insufficient"):
            raise ValueError("evidence_coverage is unsupported.")
        if (self.state == "complete" and self.evidence_coverage != "complete") or (self.state == "partial" and self.evidence_coverage == "insufficient") or (self.state == "insufficient_data" and self.evidence_coverage != "insufficient"):
            raise ValueError("Concentration state contradicts evidence coverage.")
        if self.module_id != "portfolio_concentration" or self.module_version != "1.0" or self.rule_set_version != "1.0":
            raise ValueError("Concentration identity is unsupported.")
        if self.source_module_id != "portfolio_distribution" or self.source_module_version != "1.0" or self.source_rule_set_version != "1.0":
            raise ValueError("Concentration source identity is unsupported.")
        _typed_tuple(self.dimensions, ConcentrationDimensionPresentation, "dimensions")
        if type(self.unusable_dimensions) is not tuple or any(value not in _DIMENSION_TITLES for value in self.unusable_dimensions) or len(set(self.unusable_dimensions)) != len(self.unusable_dimensions):
            raise TypeError("unusable_dimensions must contain unique supported dimension identifiers.")
        dimension_ids = tuple(item.dimension_id for item in self.dimensions)
        if dimension_ids != tuple(value for value in _DIMENSION_ORDER if value not in self.unusable_dimensions):
            raise ValueError("Concentration dimensions contradict the fixed order and unusable dimensions.")
        if self.unusable_dimensions != tuple(value for value in _DIMENSION_ORDER if value not in dimension_ids):
            raise ValueError("Unusable dimensions must retain fixed version-1 order.")

    @property
    def state_copy(self) -> str:
        return _ANALYSIS_COPY[self.state]

    @property
    def interpretation_copy(self) -> str:
        return _INTERPRETATION_COPY

    @property
    def collection_snapshot(self) -> str:
        return "Not supplied" if self.collection_snapshot_id is None else str(self.collection_snapshot_id)


@dataclass(frozen=True, slots=True)
class CurrentCollectionPortfolioPresentation:
    availability: PortfolioPresentationAvailability
    selected_destination: PortfolioDestination
    distribution: DistributionPresentation | None
    concentration: ConcentrationPresentation | None

    def __post_init__(self) -> None:
        _exact(self.availability, PortfolioPresentationAvailability, "availability")
        expected = (PortfolioDestination.DISTRIBUTION, PortfolioDestination.CONCENTRATION)
        _exact(self.selected_destination, PortfolioDestination, "selected_destination")
        if self.selected_destination not in expected:
            raise ValueError("selected_destination is unavailable.")
        available = self.availability is PortfolioPresentationAvailability.AVAILABLE
        if available != (self.distribution is not None and self.concentration is not None):
            raise ValueError("workspace availability contradicts its presentations.")
        if available:
            _exact(self.distribution, DistributionPresentation, "distribution")
            _exact(self.concentration, ConcentrationPresentation, "concentration")
            if (self.distribution.unique_owned_releases, self.distribution.owned_copies, self.distribution.duplicate_copies) != (self.concentration.unique_owned_releases, self.concentration.owned_copies, self.concentration.duplicate_copies):
                raise ValueError("Distribution and Concentration totals contradict each other.")
            if self.concentration.source_evidence_coverage != self.distribution.evidence_coverage or self.concentration.source_query_id != self.distribution.source_query_id or self.concentration.ownership_data_version != self.distribution.ownership_data_version or self.concentration.collection_snapshot_id != self.distribution.collection_snapshot_id:
                raise ValueError("Concentration provenance contradicts Distribution.")
            distributed = {item.dimension_id: item for item in self.distribution.dimensions}
            for concentrated in self.concentration.dimensions:
                source = distributed[concentrated.dimension_id]
                if concentrated.release_coverage != source.release_coverage or concentrated.copy_coverage != source.copy_coverage or concentrated.missing_release_ids != source.missing_release_ids:
                    raise ValueError("Concentration coverage contradicts Distribution.")
                order = tuple(item.category_id for item in source.categories)
                for basis in (concentrated.release_basis, concentrated.copy_basis):
                    release_basis = basis.basis_id == "release_membership"
                    expected_contributors = tuple(
                        (
                            item.category_id,
                            item.label,
                            item.release_ids,
                            item.release_share.numerator if release_basis else item.copy_share.numerator,
                        )
                        for item in source.categories
                    )
                    actual_contributors = tuple(
                        (item.category_id, item.label, item.release_ids, item.membership_count)
                        for item in basis.contributors
                    )
                    if actual_contributors != expected_contributors:
                        raise ValueError("Concentration contributors contradict complete Distribution order or facts.")
                    for first in (basis.first_three, basis.first_five):
                        if first is not None and tuple(item.category_id for item in first.contributors) != order[: first.included_count]:
                            raise ValueError("First-N contributors contradict Distribution order.")

    @property
    def scope_id(self) -> str:
        return "current_collection"

    @property
    def title(self) -> str:
        return "Current Collection Portfolio"

    @property
    def source_copy(self) -> str:
        return _SOURCE_COPY

    @property
    def navigation(self) -> tuple[PortfolioNavigationItem, ...]:
        return tuple(PortfolioNavigationItem(value) for value in (PortfolioDestination.DISTRIBUTION, PortfolioDestination.CONCENTRATION))

    @property
    def message(self) -> str:
        return "" if self.availability is PortfolioPresentationAvailability.AVAILABLE else _FAILURE_COPY


def _text(value, name):
    if type(value) is not str or not value:
        raise TypeError(f"{name} must be a non-empty string.")


def _exact(value, expected, name):
    if type(value) is not expected:
        raise TypeError(f"{name} must be {expected.__name__}.")


def _non_negative(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")


def _positive(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _positive_ids(values, name):
    if type(values) is not tuple or any(type(value) is not int or value <= 0 for value in values):
        raise TypeError(f"{name} must contain positive integers.")


def _typed_tuple(values, expected, name):
    if type(values) is not tuple or any(type(value) is not expected for value in values):
        raise TypeError(f"{name} must contain {expected.__name__} values.")


def _represents_ratio(value: Decimal, numerator: int, denominator: int) -> bool:
    if not value.is_finite():
        return False
    exact = Fraction(numerator, denominator)
    represented = Fraction(value)
    if exact == 0:
        return represented == 0
    exponent = value.as_tuple().exponent
    quantum = Fraction(10**exponent, 1) if exponent >= 0 else Fraction(1, 10 ** -exponent)
    return abs(exact - represented) < quantum
