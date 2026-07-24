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

## Portfolio Distribution 1.0

Portfolio Distribution is the second descriptive Portfolio Intelligence
module. It consumes canonical collection ownership and release metadata only.
It is independent of Portfolio Overview and consumes no Marketplace,
Opportunity, Decision Intelligence, snapshot, listing, price, or history data.
Its module ID and module version are `portfolio_distribution` and `1.0`; its
rule-set version is `1.0`.

### Supported metadata

The collection catalogue stores one opaque canonical value for artist, label,
and format, plus the owned release's supplied `released` value. Version 1.0
therefore supports these dimensions in fixed order:

1. artist;
2. label;
3. format;
4. exact release year; and
5. decade derived as `(year // 10) * 10`.

These strings are trimmed only at the application normalization boundary.
Joined artist, label, or format text is not split into an invented taxonomy.
Each supported dimension is consequently single-value membership in version
1.0.

Country, genre, and style are unavailable in canonical collection metadata.
Genre and style fields in legacy Marketplace snapshots are not collection
facts and are deliberately excluded. Title, folder, rating, notes, acquisition
date, catalogue number, and condition are stored but are not distribution
dimensions in this slice.

### Ownership and category accounting

The execution service calls the narrow, release-ordered
`owned_portfolio_metadata_rows` boundary once and converts adapter rows into
immutable facts. Repeated release rows with identical metadata are normalized
by summing quantity. Conflicting duplicate metadata excludes that identity
rather than selecting one value silently. Unique releases count once; copy
counts sum positive quantity; duplicate-copy count is copies minus unique
releases.

Every category exposes its canonical identity and display value, unique-release
and copy counts, explicit portfolio denominators, exact `Decimal` ratios, and
ascending contributing release IDs. Since all implemented dimensions are
single-valued, category totals equal releases and copies with metadata.
Future canonical multi-valued metadata may allow membership totals and shares
to exceed portfolio totals, but version 1.0 does not parse such values.

Missing metadata is never converted into an `Unknown` category. Each dimension
separately exposes releases and copies with and without metadata, exact coverage
ratios, and missing release IDs. Overall metadata coverage is:

- `complete` when every implemented dimension is present for every valid release;
- `partial` when every dimension has some usable metadata but at least one value is missing;
- `limited` when some dimensions have no usable metadata and another remains usable;
- `insufficient` for an empty portfolio or when no implemented dimension is usable.

Coverage is evidence completeness, not confidence or portfolio quality.

### Ordering, concentration, and lifecycle

Dimensions use the fixed order above. Categories use release count descending,
copy count descending, canonical display value, and category identity.
Decades use ascending decade order. Release detail uses ascending release ID.
Largest-category facts use the same count and canonical tie-break rules and
report tie counts without interpretation.

The top-level Portfolio desktop experience now contains Overview and
Distribution tabs. Both receive already-produced results. Opening Portfolio or
switching tabs performs no query, execution, normalization, aggregation,
ratio calculation, concentration calculation, or sorting.

Portfolio Distribution contains no score, valuation, recommendation,
diversification assessment, risk statement, prediction, or target allocation.
Portfolio Concentration Intelligence and Portfolio Decision Intelligence remain
deferred.

## Portfolio Concentration 1.0

Portfolio Concentration is the third descriptive Portfolio Intelligence
module. It consumes exactly one already-produced, validated Portfolio
Distribution `IntelligenceResult` with module and rule-set version `1.0`. It
does not query ownership, normalize metadata, recreate categories, or consume
Portfolio Overview or Marketplace Intelligence.

Portfolio Distribution owns category identity, ordering, membership counts,
denominators, missing metadata, and provenance. Portfolio Concentration
preserves those facts and measures mathematical clustering within each supplied
dimension. Module ID, module version, and rule-set version are
`portfolio_concentration`, `1.0`, and `1.0`.

### Membership and metrics

Release and copy memberships are analysed independently. Each basis exposes:

- membership total and represented-category count;
- largest-category numerator, denominator, share, and all tied categories;
- top-three and top-five membership totals, denominators, shares, and source
  categories;
- raw HHI;
- normalized HHI; and
- inverse-HHI effective category count.

Top-N contributors are the first N categories in Portfolio Distribution's
canonical source order. When fewer categories exist, every represented
category contributes and the share may equal one.

```text
HHI = sum((category membership / total membership)²)
effective category count = 1 / HHI
```

For more than one category:

```text
normalized HHI = (HHI - 1/N) / (1 - 1/N)
```

One category has raw HHI `1`, normalized HHI `1`, and effective category count
`1`. A dimension without represented categories has unavailable concentration
metrics; zero is not fabricated.

Release/copy differences expose copy-minus-release deltas for largest-category
share, top-three and top-five share, HHI, normalized HHI, and effective category
count. Their direction is factual and is not interpreted as better or worse.

### States and evidence

Each counting basis receives a mathematical concentration state based only on
normalized HHI. Version 1.0 defaults are:

- `dispersed`: below `0.20`;
- `moderate`: at least `0.20` and below `0.40`;
- `concentrated`: at least `0.40` and below `0.65`;
- `highly_concentrated`: at least `0.65`; and
- `insufficient`: metrics cannot be calculated.

A single represented category is `highly_concentrated`. These labels describe
the observed mathematical category distribution. They are not investment risk,
portfolio quality, or diversification advice.

Concentration evidence is:

- `complete` when every supported source dimension is usable and has complete
  release and copy metadata;
- `partial` when every supported dimension is usable but some metadata is
  missing;
- `limited` when at least one dimension is unusable and another is usable; and
- `insufficient` for an invalid source, empty portfolio, or no usable
  dimensions.

Portfolio Distribution's evidence state and all per-dimension missing metadata
facts remain separately visible. Missing values are never categories.

### Provenance, ordering, and lifecycle

Concentration preserves the Distribution module and rule-set versions,
Distribution provenance, collection snapshot identity where supplied, source
evidence state, supported dimensions, analysed dimensions, unusable dimensions,
source diagnostics, and source category order. No timestamp or identity is
invented.

The Portfolio desktop workspace contains Overview, Distribution,
Concentration, and Opportunity Alignment tabs. Each tab receives an
already-produced result. Opening the
workspace or changing tabs performs no provider call, repository query,
calculation, classification, aggregation, or sorting.

Portfolio Concentration creates no overall portfolio score, risk rating,
valuation, recommendation, target allocation, or rebalancing guidance.
Portfolio Opportunity Alignment is the first downstream Portfolio Decision
Intelligence synthesis. It requires compatible Overview, Distribution, and
Concentration 1.0 outputs and never reads collection or Marketplace data
directly. It preserves release/copy semantics and source order, and uses
Concentration states without recalculation. Its explainable assessment
interprets observed relationships, not portfolio merit, risk, expected return,
or an action.
