# Portfolio Intelligence

## Purpose

Portfolio Intelligence describes factual characteristics of the user's owned
portfolio by combining immutable ownership facts with already-produced
release-level intelligence. It automates aggregation and evidence accounting;
it does not make collection decisions.

Collection data describes what the user owns. Collection Intelligence analyses
collection characteristics. Marketplace Decision Intelligence describes
observed conditions for individual releases. Portfolio Intelligence aggregates
owned holdings across those release-level conditions. A future Portfolio
Decision Intelligence layer may interpret portfolio-level facts, but is not
part of this foundation.

```text
Owned collection facts ──────────────┐
                                     ▼
Marketplace Decision Intelligence → Portfolio Intelligence
                                     │
                                     ▼
                              IntelligenceResult
```

## Portfolio Overview 1.0

Portfolio Overview is the first Portfolio Intelligence module. It consumes
normalized owned-release facts obtained through the collection application
boundary and one already-produced Marketplace Opportunity
`IntelligenceResult`.

It does not execute Opportunity, Momentum, Stability, Scarcity, or any
lower-level intelligence. It cannot access Marketplace History, snapshots,
listings, repositories, SQLite, network clients, or a clock.

The module ID, module version, and rule-set version are respectively
`portfolio_overview`, `1.0`, and `1.0`. Registration and execution are explicit;
the default Intelligence Engine registry is unchanged.

## Ownership and matching

The collection model stores one ownership row per canonical positive Discogs
`release_id`. Repeated CSV rows are represented by the positive integer
`collection_ownership.quantity`. Portfolio Overview therefore preserves both
unique owned release count and total owned-copy count. Repeated application
rows are normalized by summing their supplied quantities and reported
diagnostically. Invalid identities or quantities are excluded and counted; no
ownership fact is inferred.

Owned releases match Opportunity release details only by `release_id`.
Opportunity-only releases may produce validation diagnostics but never appear
as owned detail. Unmatched owned releases remain visible with the explicit
`unmatched` state; no assessment is fabricated.

Release detail order is matched usable, matched insufficient, then unmatched;
Opportunity assessment order and ascending release ID complete the order.

## Evidence and distributions

Usable Opportunity evidence requires a structurally validated matched detail
whose Opportunity assessment and evidence coverage are both not
`insufficient`.

Portfolio evidence coverage uses exact `Decimal` arithmetic:

- `complete`: every valid unique owned release has usable Opportunity evidence;
- `partial`: at least the configured threshold, default `0.75`, but less than
  all valid unique owned releases has usable evidence;
- `limited`: more than zero but below that threshold has usable evidence; and
- `insufficient`: the source is missing or incompatible, the portfolio is
  empty, or no owned release has usable evidence.

The partial threshold is immutable, constructor-configurable, validated between
zero and one, and preserved in output. Coverage describes extent of compatible
evidence; it is not confidence or probability.

Opportunity, Momentum, Stability, and observed Marketplace Scarcity
distributions preserve every source enum state, including zero-count and
`insufficient` states, in explicit source order. Each entry exposes its count,
release IDs, and exact ratios against visible all-owned, matched, and
usable-Opportunity denominators. Momentum, Stability, and Scarcity values are
read only from Opportunity detail and are never independently obtained or
recalculated.

## Concentration, explanations, and provenance

For each dimension, Portfolio Overview reports only transparent concentration
facts: the first largest category in explicit enum order, its count and matched
ratio, and represented-category count. It does not use entropy, weighting,
scores, or qualitative diversification or risk labels.

Canonical reason codes and diagnostics explain matching, source compatibility,
evidence sufficiency, normalization, and category presence. Provenance
preserves the collection snapshot identity when supplied, Opportunity module
and rule-set versions, compatibility, and source evidence-window snapshot
identities already present in Opportunity. No timestamp or identifier is
invented.

## Presentation and desktop lifecycle

`PortfolioOverviewPresentationService` maps typed output into immutable view
models without matching, aggregation, ratio calculation, classification, or
sorting. Portfolio Overview is a separate top-level desktop destination rather
than a fifteenth Collection Explorer tab. Its controller accepts only an
already-produced result. Opening the view performs no collection query,
provider call, or intelligence execution.

## Deliberate exclusions

Portfolio Overview contains no valuation, cost basis, gain or loss, forecast,
confidence probability, recommendation, ranking, target allocation,
optimization, or rebalancing. Portfolio Decision Intelligence remains deferred.
No schema, migration, Marketplace serializer, Marketplace History, or
Intelligence History wire-format change is introduced.
