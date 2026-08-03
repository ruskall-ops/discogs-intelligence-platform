"""Typed Marketplace outcome adapters for shared presentation copy."""

from dip.experience.results_presentation import PresentationStateKind

from .models import MarketplaceChangePresentationOutcome


def marketplace_outcome_state_kind(
    outcome: MarketplaceChangePresentationOutcome,
) -> PresentationStateKind:
    """Map one safe typed workspace outcome to its canonical factual state."""

    if type(outcome) is not MarketplaceChangePresentationOutcome:
        raise TypeError("outcome must be a MarketplaceChangePresentationOutcome.")
    return {
        MarketplaceChangePresentationOutcome.NO_ELIGIBLE_CURRENT: (
            PresentationStateKind.INSUFFICIENT_HISTORY
        ),
        MarketplaceChangePresentationOutcome.NO_COMPATIBLE_BASELINE: (
            PresentationStateKind.INSUFFICIENT_HISTORY
        ),
        MarketplaceChangePresentationOutcome.NO_COMPARABLE_FACTS: (
            PresentationStateKind.INSUFFICIENT_DATA
        ),
        MarketplaceChangePresentationOutcome.HISTORY_UNREADABLE: (
            PresentationStateKind.ERROR
        ),
        MarketplaceChangePresentationOutcome.HISTORY_INVALID: (
            PresentationStateKind.ERROR
        ),
        MarketplaceChangePresentationOutcome.COMPARISON_FAILED: (
            PresentationStateKind.ERROR
        ),
    }[outcome]


__all__ = ["marketplace_outcome_state_kind"]
