"""Pure mapping boundaries for canonical Collector Run Marketplace capture."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceDiagnosticSeverity,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)


class ProviderFactState(str, Enum):
    """Presence and usability of one normalized provider fact."""

    MISSING = "missing"
    VALID = "valid"
    INVALID = "invalid"


class MarketplaceCaptureAttemptStatus(str, Enum):
    """Safe outcome retained for one completed provider attempt."""

    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass(frozen=True)
class ProviderMarketplaceFacts:
    """Sanitized exact provider facts safe to retain during one run."""

    wants_state: ProviderFactState
    wants: int | None
    haves: int | None
    supply_state: ProviderFactState
    copies_for_sale: int | None
    price_state: ProviderFactState
    lowest_price: Decimal | None
    currency_state: ProviderFactState
    currency: str | None
    styles: str | None
    genres: str | None
    discogs_uri: str | None


@dataclass(frozen=True)
class MarketplaceCaptureAttempt:
    """Immutable provider-neutral evidence for one requested release."""

    release_id: int
    status: MarketplaceCaptureAttemptStatus
    facts: ProviderMarketplaceFacts | None = None

    def __post_init__(self) -> None:
        if type(self.release_id) is not int:
            raise TypeError("release_id must be an integer.")
        if self.release_id <= 0:
            raise ValueError("release_id must be positive.")
        if type(self.status) is not MarketplaceCaptureAttemptStatus:
            raise TypeError("status must be a MarketplaceCaptureAttemptStatus.")
        if self.status is MarketplaceCaptureAttemptStatus.SUCCESS:
            if type(self.facts) is not ProviderMarketplaceFacts:
                raise TypeError("A successful attempt requires provider facts.")
        elif self.facts is not None:
            raise ValueError("An unsuccessful attempt cannot contain provider facts.")


def normalize_provider_facts(data: Mapping[str, Any]) -> ProviderMarketplaceFacts:
    """Copy loose provider output into exact, immutable, non-sensitive facts."""

    if not isinstance(data, Mapping):
        raise TypeError("provider data must be a mapping.")
    wants_state, wants = _count_fact(data.get("wants"))
    _, haves = _count_fact(data.get("haves"))
    supply_state, supply = _count_fact(data.get("copies_for_sale"))
    price_state, price = _price_fact(data.get("lowest_price"))
    currency_state, currency = _currency_fact(data.get("currency"))
    return ProviderMarketplaceFacts(
        wants_state=wants_state,
        wants=wants,
        haves=haves,
        supply_state=supply_state,
        copies_for_sale=supply,
        price_state=price_state,
        lowest_price=price,
        currency_state=currency_state,
        currency=currency,
        styles=_optional_text(data.get("styles")),
        genres=_optional_text(data.get("genres")),
        discogs_uri=_optional_text(data.get("discogs_uri")),
    )


def project_legacy_marketplace_facts(
    facts: ProviderMarketplaceFacts,
) -> Mapping[str, Any]:
    """Return the legacy defaults and scalar types expected by existing code."""

    if type(facts) is not ProviderMarketplaceFacts:
        raise TypeError("facts must be ProviderMarketplaceFacts.")
    usable_money = (
        facts.price_state is ProviderFactState.VALID
        and facts.currency_state is ProviderFactState.VALID
    )
    return {
        "wants": facts.wants if facts.wants is not None else 0,
        "haves": facts.haves if facts.haves is not None else 0,
        "copies_for_sale": (
            facts.copies_for_sale if facts.copies_for_sale is not None else 0
        ),
        "lowest_price": float(facts.lowest_price) if usable_money else 0.0,
        "currency": facts.currency or "",
        "styles": facts.styles or "",
        "genres": facts.genres or "",
        "discogs_uri": facts.discogs_uri or "",
    }


def successful_capture_attempt(
    release_id: int,
    facts: ProviderMarketplaceFacts,
) -> MarketplaceCaptureAttempt:
    """Create safe successful attempt evidence."""

    return MarketplaceCaptureAttempt(
        release_id,
        MarketplaceCaptureAttemptStatus.SUCCESS,
        facts,
    )


def unavailable_capture_attempt(release_id: int) -> MarketplaceCaptureAttempt:
    """Create safe evidence for a provider returning no observation."""

    return MarketplaceCaptureAttempt(
        release_id,
        MarketplaceCaptureAttemptStatus.UNAVAILABLE,
    )


def failed_capture_attempt(release_id: int) -> MarketplaceCaptureAttempt:
    """Create safe evidence for a provider exception."""

    return MarketplaceCaptureAttempt(
        release_id,
        MarketplaceCaptureAttemptStatus.FAILED,
    )


def build_marketplace_snapshot(
    analysis_run_id: int,
    captured_at: datetime,
    attempts: Sequence[MarketplaceCaptureAttempt],
) -> MarketplaceSnapshot:
    """Build one canonical aggregate from a completed Collector Run window."""

    if type(analysis_run_id) is not int:
        raise TypeError("analysis_run_id must be an integer.")
    if analysis_run_id <= 0:
        raise ValueError("analysis_run_id must be positive.")
    if type(captured_at) is not datetime:
        raise TypeError("captured_at must be a datetime.")
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware.")
    if isinstance(attempts, (str, bytes)) or not isinstance(attempts, Sequence):
        raise TypeError("attempts must be a sequence.")
    values = tuple(attempts)
    if not values:
        raise ValueError("A canonical capture requires provider attempts.")
    if any(type(value) is not MarketplaceCaptureAttempt for value in values):
        raise TypeError("attempts contains an unsupported value.")
    release_ids = tuple(value.release_id for value in values)
    if len(set(release_ids)) != len(release_ids):
        raise ValueError("attempt release IDs must not contain duplicates.")

    successful = tuple(
        value
        for value in values
        if value.status is MarketplaceCaptureAttemptStatus.SUCCESS
    )
    if not successful:
        diagnostics = _deduplicate_diagnostics(
            tuple(_attempt_diagnostic(value) for value in values)
            + (
                _diagnostic(
                    "marketplace_capture_failed",
                    "Marketplace capture completed without a usable provider observation.",
                    MarketplaceDiagnosticSeverity.ERROR,
                    attempted=str(len(values)),
                    failed=str(len(values)),
                    release_ids=",".join(str(value) for value in release_ids),
                ),
            )
        )
        return MarketplaceSnapshot(
            snapshot_id=f"collector-run-{analysis_run_id}",
            captured_at=captured_at,
            source="discogs",
            status=MarketplaceDataStatus.FAILED,
            diagnostics=diagnostics,
            source_version=None,
        )

    observations: list[MarketplaceReleaseObservation] = []
    snapshot_diagnostics: list[MarketplaceDiagnostic] = []
    for attempt in values:
        if attempt.status is MarketplaceCaptureAttemptStatus.SUCCESS:
            observation = _release_observation(attempt, captured_at)
        elif attempt.status is MarketplaceCaptureAttemptStatus.UNAVAILABLE:
            diagnostic = _attempt_diagnostic(attempt)
            observation = MarketplaceReleaseObservation(
                attempt.release_id,
                captured_at,
                MarketplaceDataStatus.UNAVAILABLE,
                diagnostics=(diagnostic,),
            )
        else:
            diagnostic = _attempt_diagnostic(attempt)
            observation = MarketplaceReleaseObservation(
                attempt.release_id,
                captured_at,
                MarketplaceDataStatus.FAILED,
                diagnostics=(diagnostic,),
            )
        observations.append(observation)
        snapshot_diagnostics.extend(observation.diagnostics)

    complete = all(
        value.status is MarketplaceDataStatus.COMPLETE for value in observations
    )
    status = (
        MarketplaceDataStatus.COMPLETE
        if complete
        else MarketplaceDataStatus.PARTIAL
    )
    return MarketplaceSnapshot(
        snapshot_id=f"collector-run-{analysis_run_id}",
        captured_at=captured_at,
        source="discogs",
        status=status,
        release_observations=tuple(observations),
        listing_observations=(),
        diagnostics=(
            ()
            if complete
            else _deduplicate_diagnostics(tuple(snapshot_diagnostics))
        ),
        source_version=None,
    )


def _release_observation(
    attempt: MarketplaceCaptureAttempt,
    captured_at: datetime,
) -> MarketplaceReleaseObservation:
    facts = attempt.facts
    assert facts is not None
    diagnostics: list[MarketplaceDiagnostic] = []
    if facts.wants_state is not ProviderFactState.VALID:
        diagnostics.append(
            _missing_fact(attempt.release_id, "num_wanted")
        )
    if facts.supply_state is not ProviderFactState.VALID:
        diagnostics.append(
            _missing_fact(attempt.release_id, "num_for_sale")
        )

    money: MarketplaceMoney | None = None
    money_required = (
        facts.supply_state is ProviderFactState.VALID
        and facts.copies_for_sale is not None
        and facts.copies_for_sale > 0
    )
    if facts.price_state is ProviderFactState.INVALID:
        diagnostics.append(
            _unusable_money(attempt.release_id, "invalid_amount")
        )
    elif facts.price_state is ProviderFactState.VALID:
        if facts.currency_state is ProviderFactState.MISSING:
            diagnostics.append(
                _unusable_money(attempt.release_id, "missing_currency")
            )
        elif facts.currency_state is ProviderFactState.INVALID:
            diagnostics.append(
                _unusable_money(attempt.release_id, "invalid_currency")
            )
        else:
            assert facts.lowest_price is not None
            assert facts.currency is not None
            money = MarketplaceMoney(facts.lowest_price, facts.currency)
    elif money_required:
        diagnostics.append(
            _missing_fact(attempt.release_id, "lowest_price")
        )

    has_facts = any(
        value is not None
        for value in (facts.wants, facts.copies_for_sale, money)
    )
    if not has_facts:
        status = MarketplaceDataStatus.EMPTY
    elif diagnostics:
        status = MarketplaceDataStatus.PARTIAL
    else:
        status = MarketplaceDataStatus.COMPLETE
    return MarketplaceReleaseObservation(
        release_id=attempt.release_id,
        observed_at=captured_at,
        status=status,
        lowest_price=money,
        num_for_sale=facts.copies_for_sale,
        num_wanted=facts.wants,
        diagnostics=_deduplicate_diagnostics(tuple(diagnostics)),
    )


def _attempt_diagnostic(
    attempt: MarketplaceCaptureAttempt,
) -> MarketplaceDiagnostic:
    if attempt.status is MarketplaceCaptureAttemptStatus.UNAVAILABLE:
        return _diagnostic(
            "provider_observation_unavailable",
            "The marketplace source returned no release observation.",
            MarketplaceDiagnosticSeverity.WARNING,
            release_id=str(attempt.release_id),
        )
    return _diagnostic(
        "provider_request_failed",
        "The marketplace source request failed.",
        MarketplaceDiagnosticSeverity.ERROR,
        release_id=str(attempt.release_id),
    )


def _missing_fact(release_id: int, field: str) -> MarketplaceDiagnostic:
    return _diagnostic(
        "marketplace_fact_missing",
        "An expected marketplace fact was not supplied.",
        MarketplaceDiagnosticSeverity.WARNING,
        release_id=str(release_id),
        field=field,
    )


def _unusable_money(release_id: int, reason: str) -> MarketplaceDiagnostic:
    return _diagnostic(
        "marketplace_money_unusable",
        "Supplied marketplace money could not be represented safely.",
        MarketplaceDiagnosticSeverity.WARNING,
        release_id=str(release_id),
        field="lowest_price",
        reason=reason,
    )


def _diagnostic(
    code: str,
    message: str,
    severity: MarketplaceDiagnosticSeverity,
    **details: str,
) -> MarketplaceDiagnostic:
    return MarketplaceDiagnostic(code, message, severity, details)


def _deduplicate_diagnostics(
    values: tuple[MarketplaceDiagnostic, ...],
) -> tuple[MarketplaceDiagnostic, ...]:
    result: list[MarketplaceDiagnostic] = []
    seen: set[tuple[object, ...]] = set()
    for value in values:
        key = (
            value.code,
            value.severity,
            tuple(sorted(value.details.items())),
        )
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _count_fact(value: Any) -> tuple[ProviderFactState, int | None]:
    if value is None:
        return ProviderFactState.MISSING, None
    if type(value) is not int or value < 0:
        return ProviderFactState.INVALID, None
    return ProviderFactState.VALID, value


def _price_fact(value: Any) -> tuple[ProviderFactState, Decimal | None]:
    if value is None:
        return ProviderFactState.MISSING, None
    if type(value) is int:
        if value < 0:
            return ProviderFactState.INVALID, None
        return ProviderFactState.VALID, Decimal(value)
    if type(value) is Decimal and value.is_finite() and value >= 0:
        return ProviderFactState.VALID, value
    return ProviderFactState.INVALID, None


def _currency_fact(value: Any) -> tuple[ProviderFactState, str | None]:
    if value is None:
        return ProviderFactState.MISSING, None
    if (
        isinstance(value, str)
        and len(value) == 3
        and value.isascii()
        and value.isalpha()
        and value == value.upper()
    ):
        return ProviderFactState.VALID, value
    return ProviderFactState.INVALID, value if isinstance(value, str) else None


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


__all__ = [
    "MarketplaceCaptureAttempt",
    "MarketplaceCaptureAttemptStatus",
    "ProviderFactState",
    "ProviderMarketplaceFacts",
    "build_marketplace_snapshot",
    "failed_capture_attempt",
    "normalize_provider_facts",
    "project_legacy_marketplace_facts",
    "successful_capture_attempt",
    "unavailable_capture_attempt",
]
