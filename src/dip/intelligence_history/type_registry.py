"""Explicit immutable value types approved for Intelligence History."""

from dataclasses import is_dataclass
from typing import Any

from dip.intelligence.modules.hidden_gems import HiddenGemCandidate
from dip.intelligence.modules.historical_intelligence import (
    HistoricalComparison,
    HistoricalReleaseChange,
    HistoricalReleaseIdentity,
    HistoricalSnapshotInfo,
)
from dip.marketplace_intelligence.models import MarketplaceDiagnostic, MarketplaceMoney
from dip.marketplace_intelligence.price_changes import (
    ListingPriceChange,
    PriceChangeDelta,
    PriceChangesOutput,
    PriceChangesSnapshotReference,
    PriceChangesSummary,
    ReleasePriceChange,
)
from dip.marketplace_intelligence.supply_changes import (
    ReleaseSupplyChange,
    SupplyChangesOutput,
    SupplyChangesSnapshotReference,
    SupplyChangesSummary,
)
from dip.marketplace_intelligence.rare_appearances import (
    RareAppearance,
    RareAppearanceSnapshotReference,
    RareAppearancesOutput,
    RareAppearancesSummary,
)
from dip.marketplace_intelligence.marketplace_activity import (
    MarketplaceActivityObservationReference,
    MarketplaceActivityOutput,
    MarketplaceActivitySummary,
    ReleaseActivity,
)
from dip.marketplace_intelligence.weekend_listings import (
    WeekendListingCandidate,
    WeekendListingsOutput,
    WeekendWindow,
)


APPROVED_DATACLASS_TYPES: dict[str, type[Any]] = {
    f"{value_type.__module__}.{value_type.__qualname__}": value_type
    for value_type in (
        HiddenGemCandidate,
        HistoricalComparison,
        HistoricalReleaseChange,
        HistoricalReleaseIdentity,
        HistoricalSnapshotInfo,
        MarketplaceDiagnostic,
        MarketplaceMoney,
        ListingPriceChange,
        PriceChangeDelta,
        PriceChangesOutput,
        PriceChangesSnapshotReference,
        PriceChangesSummary,
        ReleasePriceChange,
        ReleaseSupplyChange,
        SupplyChangesOutput,
        SupplyChangesSnapshotReference,
        SupplyChangesSummary,
        RareAppearance,
        RareAppearanceSnapshotReference,
        RareAppearancesOutput,
        RareAppearancesSummary,
        MarketplaceActivityObservationReference,
        MarketplaceActivityOutput,
        MarketplaceActivitySummary,
        ReleaseActivity,
        WeekendListingCandidate,
        WeekendListingsOutput,
        WeekendWindow,
    )
}


def approved_dataclass_name(value: Any) -> str | None:
    """Return the stable registry name for an approved dataclass value."""

    value_type = type(value)
    name = f"{value_type.__module__}.{value_type.__qualname__}"
    if is_dataclass(value) and APPROVED_DATACLASS_TYPES.get(name) is value_type:
        return name
    return None
