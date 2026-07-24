# Marketplace Architecture

## Purpose

Marketplace Architecture defines how the Discogs Intelligence Platform (DIP) acquires, stores, updates and exposes marketplace information.

The objective is to provide a reusable foundation for every future Marketplace Intelligence capability while remaining independent from presentation, user interface and individual intelligence modules.

Marketplace Architecture should allow future intelligence modules to answer questions such as:

- Is demand increasing?
- Is supply becoming scarce?
- Is an artist gaining momentum?
- Is a release undervalued relative to comparable releases?
- Is a label becoming more collectible?
- How has marketplace behaviour changed over time?

The architecture is intentionally generic.

Individual Marketplace Intelligence modules build upon this foundation rather than introducing their own storage or data acquisition systems.

---

# Philosophy

Marketplace data is another source of evidence.

It should be treated in exactly the same way as collection data:

```text
Marketplace Data
        ↓
Marketplace Snapshot
        ↓
Marketplace Context
        ↓
Marketplace Intelligence
        ↓
Dashboard / Explorer
```

Marketplace Intelligence should remain:

- deterministic;
- explainable;
- evidence-based;
- presentation-independent.

It must never recommend buying or selling.

It exists to support research.

---

# Design Goals

The Marketplace Architecture should:

- isolate external APIs from intelligence modules;
- minimise unnecessary API requests;
- preserve historical marketplace observations;
- support deterministic intelligence calculations;
- allow offline analysis;
- support future caching;
- remain independent of presentation;
- support future data providers.

---

# Guiding Principle

Marketplace Intelligence should consume marketplace data.

It should never be responsible for collecting marketplace data.

The architecture therefore separates:

```text
Data acquisition

↓

Data persistence

↓

Data access

↓

Intelligence modules
```

Each layer has a single responsibility.

---

# High-Level Architecture

## Intelligence category boundaries

Marketplace intelligence uses three explicit categories:

- **Primary Intelligence** derives typed observations directly from the
  application-supplied Marketplace snapshot or history context. Price Changes,
  Supply Changes, Rare Appearances, and Listing Lifecycle are primary modules.
- **Composite Intelligence** combines already-produced intelligence into a new
  factual view without repeating the source calculations. Marketplace Activity
  is composite intelligence.
- **Decision Intelligence** synthesizes already-produced intelligence through
  explicit, versioned rules to support a human decision. It exposes its
  components, coverage, provenance, and reasons rather than hiding them in an
  opaque score.

Decision Intelligence does not receive raw Marketplace snapshots, select or
query history, access repositories, or execute its source modules. It remains
non-prescriptive: it may describe evidence and a qualified assessment, but must
not forecast outcomes or recommend buying, selling, or trading.

## Supply Changes Intelligence

The first Supply Changes slice compares exactly two snapshots selected by the
application layer. `SupplyChangesExecutionService` performs one bounded
`recent_snapshots(2)` query and runs an explicitly registered
`SupplyChangesModule`. The module never selects history, uses persistence,
reads the clock, or derives supply from listing observations.

Its authoritative input is the provider-supplied release observation
`supply_count` domain property, a backwards-compatible name for the existing
version-1 `num_for_sale` field. Releases align only by `release_id`. Comparable
integer values produce the exact signed `latest - previous` delta. Missing
facts become newly available, no longer available, or incomparable without a
fabricated zero. Unchanged releases are counted but omitted from detail, and
emitted records use ascending release ID order.

Complete and empty snapshot pairs are valid. Partial inputs or incomparable
records produce a partial result with preserved source diagnostics.
Unavailable inputs are skipped and failed inputs fail. The standard
`IntelligenceResult` contains immutable typed output under stable module ID
`supply_changes`, version `1.0`; the default engine registry remains unchanged.

## Rare Appearances Intelligence

Rare Appearances reports historical release-observation frequency without
interpreting price, supply, demand, desirability, or investment quality. Its
application execution service retrieves complete Marketplace History once
through `all_snapshots()`, which returns deterministic chronological order by
capture time and snapshot ID. The domain module receives the immutable tuple
and performs no repository or persistence access.

A release appears whenever its `MarketplaceReleaseObservation` exists in a
snapshot; listings and other supplied facts are irrelevant. Unavailable and
failed snapshots are excluded, partial snapshots contribute with diagnostics,
and empty snapshots count as valid history. For each release the module records
the first and latest observations, observation snapshot IDs, exact appearance
count, analyzed history size, Decimal ratio, and longest internal absence.
Leading and trailing absence is ignored.

The constructor threshold defaults to fewer than three appearances. Included
records are ordered by appearance count ascending, longest absence descending,
then release ID ascending. The standard `IntelligenceResult` contains immutable
typed output under module ID `rare_appearances`, version `1.0`. Registration is
explicit and does not alter the default engine registry.

## Marketplace Activity Intelligence

Marketplace Activity is the first composite Marketplace Intelligence module.
Its execution service coordinates already-produced Price Changes, Supply
Changes, and Rare Appearances results, validates their snapshot identities, and
then executes Marketplace Activity once. Weekend Listings may be supplied but
is not required. The composite module never receives or analyzes Marketplace
snapshots and never executes its source modules.

Release profiles are anchored to the threshold-qualified typed appearances
exposed by Rare Appearances. Price and supply event counts are aggregated from
their existing typed change records by `release_id`; no comparison, delta, or
appearance logic is repeated. Source change records without corresponding
appearance detail are reported diagnostically rather than reconstructed.

Each immutable profile preserves appearance count and Decimal ratio, price and
supply change counts, longest internal absence, and first/latest observation
references. Total activity is the transparent sum of those factual event
counts. Profiles are ordered by total activity descending, appearance count
ascending, then release ID ascending. Module ID is `marketplace_activity`,
version `1.0`, with explicit registration only.

## Listing Lifecycle Intelligence

Listing Lifecycle is a primary Marketplace Intelligence module that describes
listing-presence sequences across complete Marketplace History. Its execution
service performs one `all_snapshots()` query and supplies the immutable
chronological tuple to the domain module. The module has no repository, SQLite,
network, presentation, or clock dependency.

Listings use `(release_id, listing_id)` identity. Complete, partial, and empty
snapshots are analyzable; unavailable and failed snapshots are excluded with
factual diagnostics because they cannot establish listing absence. Therefore
the exposed history size and latest boundary mean analyzed Marketplace
history. Partial snapshots contribute normally and make the result partial.

For each observed listing the module exposes exact first/latest observations,
snapshot count and Decimal ratio, current presence, longest continuous observed
run, disappearance/reappearance transition counts, and longest internal
absence. Leading and trailing absences do not affect longest absence.

States are deterministic sequence labels. `new` first appears at the latest
analyzed snapshot; `active` remains continuously observed through it;
`reappeared` is currently present after one return; `intermittent` is currently
present after repeated returns; `disappeared` has one trailing non-observation;
and `ended` has at least two. `Ended` does not infer sale, withdrawal, expiry,
or any other cause. Ordering uses this state order, then observation ratio
descending, release ID, and listing ID. Module ID is `listing_lifecycle`,
version `1.0`, and registration remains explicit.

## Marketplace Momentum Decision Intelligence

Marketplace Momentum is the first Decision Intelligence module. Its required
sources are already-produced Price Changes, Supply Changes, and Marketplace
Activity results. Rare Appearances and Listing Lifecycle results are optional
supporting sources. The application-owned
`MarketplaceMomentumExecutionService` invokes each direct source provider once,
validates and normalizes the returned results, and executes the dedicated
Marketplace Momentum engine once. The decision module receives only immutable
normalized facts; it never receives snapshots, queries history, accesses a
repository, or executes a source module.

The result keeps its reasoning transparent. For every release it exposes the
price-direction component, supply-pressure component, Marketplace Activity
level, evidence coverage, assessment, stable reason codes, and source
provenance. Price direction uses the signed balance of comparable price
increases and decreases. Supply pressure reverses the supply balance: decreases
are positive pressure and increases are negative pressure. Availability and
incomparability events remain visible counts but are not treated as directional
evidence. Activity levels use explicit thresholds: zero is `none`, one or two
events are `low`, three through five are `moderate`, and more than five are
`high`. An absent Activity profile is `insufficient`, not a factual zero.

Coverage is deterministic. No comparable price or supply evidence is
`insufficient`; exactly one comparable dimension, or no Activity profile, is
`limited`; partial required source evidence or diagnostics is `partial`; and
otherwise coverage is `complete`. Assessment is likewise rule based: aligned
positive price evidence and positive or neutral supply pressure is `positive`;
aligned negative price evidence and negative or neutral supply pressure is
`negative`; opposing directions, one directional component without its
counterpart, or neutral-versus-directional evidence is `mixed`; two neutral
components, or one neutral component with the other unavailable, is `neutral`;
and the absence of comparable evidence in both directional dimensions is
`insufficient`. These labels describe the supplied evidence and are not
predictions or recommendations.

Required source provenance must identify one coherent comparison. Price and
Supply must refer to the same exact previous/latest snapshot pair and compatible
capture times, source, status, and source version. Marketplace Activity must
have been built from that same pair, its Price and Supply counts must agree with
the direct results, and the pair must be the latest pair in Activity's analyzed
history. Optional Rare Appearances and Listing Lifecycle histories must match
that Activity history; overlapping Rare appearance facts must also agree.
Incompatible required evidence yields an insufficient result without release
assessments. Incompatible optional evidence is excluded diagnostically and
keeps otherwise usable core analysis partial.

The release population is the union of identity-bearing Price, Supply, and
Marketplace Activity facts. Optional evidence cannot introduce a release.
Source shapes impose deliberate limits: Price and Supply omit unchanged
per-release details, so absence of a change record is not neutral evidence;
Supply exposes at most one change record per release, so neutral supply pressure
cannot be inferred; and an absent Activity profile is not equivalent to zero
activity. `none` is reserved for an explicitly supplied factual zero.

Release order is canonical: assessment order `positive`, `mixed`, `neutral`,
`negative`, `insufficient`; then coverage order `complete`, `partial`, `limited`,
`insufficient`; then Activity order `high`, `moderate`, `low`, `none`,
`insufficient`; then total Activity descending and release ID ascending. Module
ID is `marketplace_momentum`, module version is `1.0`, and rule-set version is
`1.0`. Intelligence History support is an additive explicit type and enum
registration; it does not change the default engine registry, history wire
format, or Marketplace serializer.

## Marketplace Stability Decision Intelligence

Marketplace Stability is the second Decision Intelligence module. Its required
sources are already-produced Marketplace Activity and Listing Lifecycle
results. Optional Price Changes, Supply Changes, Rare Appearances, and
Marketplace Momentum results contribute provenance or factual context only.
Momentum describes observed direction; Stability describes observed
consistency. Neither is a recommendation or forecast.

Stability uses Activity's existing historical price- and supply-change counts
and appearance facts. It aggregates supplied Lifecycle facts by release ID to
expose listing-state counts, current-presence and persistence ratios, and
disappearance/reappearance totals. It never compares snapshots, reconstructs
appearance or listing sequences, or infers why a listing disappeared.

Each result exposes separate price, supply, appearance, listing-persistence,
and evidence-coverage components. Explicit immutable thresholds define the
stable, mixed, and volatile bands. `Volatile` describes repeated or
concentrated observed changes only and is not a financial-risk claim or
prediction. Canonical reason codes, source provenance, diagnostics, module
version `1.0`, and rule-set version `1.0` make every assessment reconstructable.
The execution service owns source acquisition and compatibility validation; the
domain has no raw-history, repository, persistence, network, or clock access.

## Marketplace Scarcity Decision Intelligence

Marketplace Scarcity is the third Decision Intelligence module. Required
already-produced sources are Rare Appearances and Listing Lifecycle. Optional
Marketplace Activity and Supply Changes provide factual supply context, while
Marketplace Stability and Marketplace Momentum are independent display context
only. They cannot alter version `1.0` Scarcity classification.

Scarcity means limited observed Marketplace availability within the supplied
evidence. It is distinct from absolute rarity, pressing quantity, edition size,
desirability, investment quality, and predicted future scarcity. Momentum
describes direction; Stability describes consistency; Scarcity describes
limited observed availability.

The release-level result exposes currently present listing bands, exact Decimal
appearance ratios, listing-state and persistence aggregation, optional supply
facts, evidence coverage, canonical reason codes, provenance, and diagnostics.
Thresholds are immutable, validated, constructor-configurable, and preserved in
the output. The module never analyzes snapshots, reconstructs appearance or
listing sequences, infers sales or production totals, or accesses history,
repositories, persistence, the network, or a clock. Module and rule-set
versions are both `1.0`.

## Marketplace Opportunity Decision Intelligence synthesis

Marketplace Opportunity is the first synthesis module over existing Decision
Intelligence dimensions. It requires already-produced Marketplace Momentum,
Marketplace Stability, and Marketplace Scarcity results and accepts no
lower-level intelligence inputs.

The application service validates typed outputs, module and rule-set versions,
release identities, diagnostics, and the strongest common evidence-window
identity exposed by source provenance. It obtains each source once and
explicitly executes one Opportunity module. Missing or incompatible dimensions
produce insufficient evidence; Opportunity never recreates a source module's
responsibility.

The immutable output preserves direction, consistency, and observed
availability assessments separately, along with each source evidence state and
an explicit supportive, neutral, limiting, adverse, or unusable mapping.
Canonical rules synthesize these facts into strong, developing, balanced,
constrained, weak, or insufficient observed alignment. There is no numerical
score, weighting, confidence probability, valuation, forecast, or
recommendation. Module and rule-set versions are both `1.0`.

Marketplace Opportunity may feed the separate Portfolio Intelligence layer.
Portfolio Overview combines that already-produced result with owned-release
facts. It does not reach through Opportunity into Marketplace History,
snapshots, listings, or lower-level Marketplace Intelligence and does not
recalculate any Decision Intelligence dimension.

```text
Marketplace Decision Intelligence
        │
        ▼
Marketplace Opportunity
        │
        ▼
Portfolio Intelligence
        │
        ▼
Portfolio Opportunity Alignment
```

Portfolio Opportunity Alignment is downstream Portfolio Decision Intelligence.
It consumes Portfolio Overview, Distribution, and Concentration only, never
Marketplace Opportunity or Marketplace source data directly. Marketplace
Opportunity reaches this synthesis solely through Overview's preserved
release-level facts.

```text
                Discogs API
                     │
                     ▼
        Marketplace Import Service
                     │
                     ▼
         Marketplace Snapshot Store
                     │
                     ▼
      Marketplace Repository Interface
                     │
                     ▼
          Marketplace Context Builder
                     │
                     ▼
          Intelligence Context
                     │
                     ▼
Marketplace Intelligence Modules
                     │
                     ▼
Dashboard / Explorer
```

---

# Marketplace Snapshot

Marketplace information should never be queried directly by intelligence modules.

Instead, every import creates a Marketplace Snapshot.

A Marketplace Snapshot represents the state of the marketplace at one point in time.

Examples include:

- lowest price;
- median price;
- highest price;
- number for sale;
- number wanted;
- last sold date;
- marketplace listings;
- marketplace statistics.

Snapshots become the historical foundation for future trend analysis.

---

# Why Snapshots?

Suppose a release currently has:

```text
For Sale:
42

Wanted:
315
```

Without snapshots, DIP only knows today's values.

With snapshots:

```text
1 Jan
For Sale: 58

Wanted: 210

↓

1 Feb
For Sale: 49

Wanted: 250

↓

1 Mar
For Sale: 42

Wanted: 315
```

The platform can now identify:

- demand growth;
- supply reduction;
- changing scarcity;
- marketplace momentum.

History creates intelligence.

---

# Marketplace Snapshot Model

Suggested model:

```python
@dataclass(frozen=True)
class MarketplaceSnapshot:
    release_id: int
    captured_at: datetime

    lowest_price: Decimal | None
    median_price: Decimal | None
    highest_price: Decimal | None

    num_for_sale: int | None
    num_wanted: int | None

    last_sold: date | None

    currency: str
```

Additional attributes may be added over time without changing the architecture.

## Implemented foundation contract

The first Marketplace Intelligence foundation is implemented as the peer domain
package `dip.marketplace_intelligence`. It contains immutable models and
deterministic serialization only. It does not fetch, persist, refresh or present
Marketplace data.

The package distinguishes four responsibilities:

- `MarketplaceListingObservation` is one specific offer observed at a supplied
  time. It contains the offer price and optional shipping, condition and seller
  region facts. It contains no opportunity or desirability interpretation.
- `MarketplaceReleaseObservation` contains provider-supplied release-level
  facts such as price bounds, supply, demand and last-sold date. Its constructor
  validates those facts but does not calculate aggregates.
- `MarketplaceSnapshot` is the observation-window aggregate. It owns the source,
  capture time, release observations, optional listing observations, capture
  status and diagnostics.
- `MarketplaceModuleResult` pairs a stable Marketplace execution context with
  the existing standard `IntelligenceResult`. It is a history-ready envelope,
  not a replacement module-result hierarchy.

Release observations are canonical by `release_id`. Listing observations are
canonical by `(release_id, listing_id)`. Their source order carries no domain
meaning, so construction defensively copies and canonicalises these sequences.
Diagnostic and execution snapshot-reference order is preserved because those
sequences may explain source or execution chronology.

## Status semantics

`MarketplaceDataStatus` uses the following explicit meanings:

| Status | Meaning |
|---|---|
| `complete` | A successful capture containing supplied marketplace facts |
| `partial` | Some usable facts exist, with diagnostics explaining incomplete capture |
| `empty` | A valid capture produced no observations or facts |
| `unavailable` | The marketplace source could not provide data |
| `failed` | The capture failed and contains no successful observations |

An observed release with `num_for_sale=0` is a supplied marketplace fact and is
therefore distinct from an empty or unavailable release. Partial, unavailable
and failed values require diagnostics. Failed snapshots and failed module-result
envelopes cannot contain successful derived records.

## Money and currency policy

`MarketplaceMoney` uses `Decimal` exclusively and never accepts or converts a
binary floating-point amount. Amounts must be finite and non-negative. Missing
money is represented by an optional field containing `None`; it is never
represented by a fabricated zero.

Currency remains attached to every amount. The foundation accepts a strict
uppercase three-letter ASCII currency identifier and performs no case
normalisation, allow-list lookup, exchange-rate conversion or cross-currency
comparison. Prices within one release observation, and price and shipping
within one listing observation, must use the same currency.

## Timestamp and identifier policy

All Marketplace datetimes must be explicitly supplied and timezone-aware.
Models never read the current clock. Original offsets are preserved in
ISO-8601 serialization; UTC normalisation is used only when validating temporal
ordering. Release, listing, snapshot and execution identifiers are supplied by
the caller and are never generated during construction or deserialization.

## Immutability and diagnostics

All public Marketplace models are frozen dataclasses. Caller-supplied
collections are copied into tuples, result mappings are recursively frozen, and
diagnostic detail mappings accept only deterministic string keys and values.
Diagnostics use stable codes, typed severity and domain-facing messages; they do
not contain UI state or raw traceback objects.

## Deterministic serialization

`serialization.py` defines explicit snapshot and module-result operations. The
top-level schema version is `1`. Serialized trees contain JSON-compatible
primitives only; decimals use exact strings, enums use their stable values and
aware datetimes use ISO-8601 strings. Mapping keys and observation collections
use their documented canonical order, while canonical JSON also sorts object
keys and uses compact separators.

Deserialization requires the exact documented keys and schema version. It
rejects duplicate JSON keys, unknown enum values, naive or malformed timestamps,
invalid decimals, non-finite numeric values, malformed records and unknown
tagged metric values. It never invents identifiers or timestamps and never
silently discards a record.

The format is domain serialization, not persistence. No repository, SQLite
schema or migration is introduced by the Marketplace Intelligence
model-and-serialization foundation itself.

---

# Marketplace Repository

Persisted aggregate snapshots are accessed through the implemented
Marketplace History repository. Its domain-facing interface is:

```python
class MarketplaceHistoryRepository(Protocol):

    def save_snapshot(
        self,
        snapshot: MarketplaceSnapshot,
    ) -> None:
        ...

    def get_snapshot(
        self,
        snapshot_id: str,
    ) -> MarketplaceSnapshot | None:
        ...

    def latest_snapshot(
        self,
    ) -> MarketplaceSnapshot | None:
        ...

    def recent_snapshots(
        self,
        limit: int,
    ) -> tuple[MarketplaceSnapshot, ...]:
        ...

    def previous_snapshot(
        self,
        snapshot_id: str,
    ) -> MarketplaceSnapshot | None:
        ...
```

The repository returns complete immutable observation-window aggregates, not
release-specific rows. Intelligence modules still receive supplied context and
do not query this repository directly. They should never know whether data
originated from:

- Discogs;
- cached data;
- local storage;
- future providers.

---

# Marketplace Import Service

The Marketplace Import Service is responsible for communicating with external APIs.

Responsibilities include:

- rate limiting;
- retries;
- authentication;
- provider-specific mapping;
- error handling;
- snapshot creation.

It is **not** responsible for intelligence.

---

# Marketplace Context

Marketplace modules should not query repositories directly.

Instead they receive marketplace information through a Marketplace Context.

```text
Repository

↓

Marketplace Context

↓

Marketplace Module
```

Suggested model:

```python
@dataclass(frozen=True)
class MarketplaceContext:
    latest_snapshots: Mapping[int, MarketplaceSnapshot]
```

Future versions may include:

- historical lookup;
- exchange rates;
- cached calculations;
- provider metadata.

---

# Relationship with IntelligenceContext

Marketplace Context should become another component of the existing IntelligenceContext.

Conceptually:

```python
IntelligenceContext

├── Collection
├── Historical Collection
├── Marketplace
└── Configuration
```

This keeps every intelligence module using the same dependency.

---

# Marketplace Cache

Marketplace requests should not occur during intelligence execution.

Instead:

```text
Scheduled Import

↓

Snapshot Database

↓

Intelligence Engine
```

This provides:

- deterministic execution;
- offline capability;
- reproducible results;
- faster dashboard loading.

---

# Refresh Strategy

Marketplace data changes independently of collection data.

Possible refresh schedules:

| Data | Frequency |
|--------|----------|
| User collection | On import |
| Marketplace | Daily |
| Exchange rates | Daily |
| Intelligence | On demand |

Refresh schedules may become configurable.

---

# Historical Marketplace Data

Marketplace snapshots should never overwrite previous observations.

Every refresh creates another historical snapshot.

```text
Release 12345

↓

1 Jan Snapshot

↓

2 Jan Snapshot

↓

3 Jan Snapshot
```

This enables:

- trend detection;
- rolling averages;
- moving momentum;
- volatility analysis.

## Implemented Marketplace History foundation

Marketplace History is implemented as a peer boundary to Marketplace
Intelligence and Intelligence History. It preserves raw, immutable
`MarketplaceSnapshot` aggregates; it does not store module conclusions or make
comparison decisions.

```text
Already-created MarketplaceSnapshot
                │
                ▼
MarketplaceHistoryCommandService
                │
                ▼
MarketplaceHistoryRepository
                │
                ▼
SQLiteMarketplaceHistoryRepository
                │
                ▼
marketplace_snapshots
```

The domain-facing repository is append-only. Saving a new stable `snapshot_id`
inserts one fact. Saving the exact same canonical snapshot again is an
idempotent no-op. Reusing that identifier for different content raises an
explicit conflict and never overwrites the original observation. The command
service accepts only an already-constructed valid snapshot; it does not fetch
data, choose a timestamp, generate an identifier or run intelligence.

The SQLite table `marketplace_snapshots` is deliberately distinct from the
legacy per-release `market_snapshots` table. It stores the stable snapshot ID,
a UTC-normalised capture-time ordering key, source, status, Marketplace schema
version and the exact canonical JSON payload. The payload produced by the
public Marketplace serializer is authoritative. Release and listing
observations are not duplicated into relational tables, and money never passes
through a floating-point storage column.

The original timezone offset remains in the canonical payload. The normalised
UTC column exists only for chronological queries. Newest-first queries use the
complete order:

```text
captured_at DESC
snapshot_id DESC
```

The previous-snapshot query follows this same global order. It does not filter
by source or status and does not decide whether two snapshots are analytically
comparable. Future modules own that decision.

Every valid status is preserved, including `empty`, `unavailable` and
`failed`, because capture absence and failure are historical audit facts. On
retrieval, the adapter deserializes through the strict public Marketplace
serializer and cross-checks the indexed ID, time, source, status, schema
version and canonical payload. Malformed JSON, unsupported versions and
metadata disagreement fail with an explicit history-integrity error; stored
data is never skipped or repaired silently.

Writes use the shared database transaction boundary. Canonical serialization
occurs before mutation, and an active caller transaction is isolated with the
existing savepoint policy. A complete snapshot is therefore stored atomically
or not at all.

`MarketplaceHistoryQueryService` exposes full immutable snapshots by ID,
latest snapshot, immediate predecessor and bounded recent history. Recent
history defaults to 20 snapshots and accepts explicit limits from 1 through
100. Singular absence is `None`; plural absence is an empty tuple. Queries
preserve repository order and do not calculate intelligence, compare
snapshots, format presentation values or contact a provider.

The first persistence slice performs no automatic capture or backfill. It is
not consumed by the Dashboard, Explorer or desktop UI, and it adds no
scheduling, caching or network behaviour.

Price Changes can consume two of these stored observations through explicit
application orchestration. Rare Appearances, Supply Trends and stronger
Weekend newness remain future consumers. Weekend Listings still means only
"observed within the supplied weekend window"; it does not compare the current
snapshot with a prior snapshot to establish newness.

---

# Marketplace Intelligence Modules

Future modules may include:

## Supply Trends

Analyse changes in:

- number for sale;
- listing velocity;
- supply growth;
- scarcity.

---

## Demand Trends

Analyse:

- wanted count;
- wanted growth;
- demand acceleration;
- collector interest.

---

## Price Momentum

Analyse:

- median movement;
- lowest price movement;
- volatility;
- appreciation.

---

## Artist Momentum

Aggregate marketplace behaviour across releases.

Possible indicators:

- rising wanted counts;
- rising prices;
- growing scarcity.

---

## Label Activity

Analyse labels rather than individual releases.

Possible metrics include:

- average appreciation;
- supply trends;
- release performance.

---

# Marketplace Intelligence Results

Marketplace modules should continue returning the standard IntelligenceResult.

They should not introduce a different result type.

```text
Marketplace Context

↓

Marketplace Module

↓

IntelligenceResult
```

The foundation's `MarketplaceModuleResult` is an immutable execution envelope
around that standard result. It preserves the Marketplace execution identifier,
ordered snapshot references and execution timestamp for deterministic
serialization. Module-specific typed outputs remain the responsibility of each
future module; the foundation does not invent a generic opportunity record or
opaque recommendation payload.

This allows:

- Dashboard integration;
- Explorer integration;
- Intelligence History;
- future comparison layers.

Module-specific presentation may project the typed output, but it does not
change the standard result contract.

---

# Relationship with Intelligence History

Future Marketplace Intelligence should participate in Intelligence History
through the standard `IntelligenceResult` contract.

```text
Marketplace Snapshot

↓

Marketplace Intelligence

↓

IntelligenceResult

↓

Intelligence History
```

Marketplace snapshots preserve the raw market.

Intelligence History preserves the conclusions drawn from that market.

These solve different problems.

Marketplace serialization does not write Intelligence History. Raw snapshots
may now be preserved through the peer Marketplace History boundary, while
future Marketplace module results continue to use the standard result contract
and may be recorded through Intelligence History. Neither history changes the
meaning or persistence format of the other.

## Weekend Listings Intelligence

Weekend Listings is the first deterministic Marketplace Intelligence module.
It consumes an immutable `MarketplaceSnapshot`, collection membership from the
standard `IntelligenceContext`, and an explicit timezone-aware weekend window.
The strict window is Saturday 00:00 inclusive to Monday 00:00 exclusive; the
module does not read a clock or infer the machine timezone.

For this slice, "observed during the weekend window" means only that the
listing observation timestamp falls inside the supplied window. A single
snapshot cannot prove that a listing is new to the marketplace, so the module
does not make that claim. A listing qualifies when its release identifier is
present in the supplied collection, its observation is inside the window, its
identifiers and price are valid under the snapshot contract, and the snapshot
status permits evaluation. Shipping, condition, seller region, artist, and
title remain optional evidence and do not exclude a listing.

`COMPLETE` snapshots are evaluated normally, `PARTIAL` snapshots retain valid
listings and source diagnostics, and `EMPTY` snapshots produce a completed
empty result. `UNAVAILABLE` and absent inputs produce a skipped result, while a
`FAILED` snapshot produces a failed result. Candidates are ordered by observed
timestamp descending, then release identifier and listing identifier ascending.
This order is part of the typed `WeekendListingsOutput` contract.

Prices and shipping use exact `MarketplaceMoney` values. They remain separate;
the module performs no floating-point conversion, currency conversion,
cross-currency comparison, total calculation, or price-based ranking. Each
candidate carries stable factual inclusion evidence, and source diagnostics
remain available at result level.

The module returns the standard `IntelligenceResult`; its typed output is
allowed by the existing Intelligence History serialization registry without a
history format or Marketplace serialization schema change. It is not in the
default engine registry yet because the current composition boundary has no
Marketplace snapshot or explicit weekend window to supply. Callers may execute
it through the existing module contract once those inputs are available.

The Weekend Listings slice deliberately excludes Marketplace fetching and
history persistence, monitoring, scheduling, scoring, recommendations, user
sorting, and filtering. Its Explorer presentation consumes an already-produced
result and never runs the module on navigation.

## Price Changes Intelligence

Price Changes is the first two-snapshot Marketplace Intelligence module. It
compares exactly the previous and latest immutable snapshots supplied in a
dedicated `MarketplaceSnapshotComparisonInput` through
`IntelligenceContext.marketplace_comparison`. The existing singular
`marketplace_snapshot` input remains the Weekend Listings boundary.

Snapshot selection and price comparison remain separate responsibilities:

```text
MarketplaceHistoryQueryService
              │
              ▼
PriceChangesExecutionService
              │
              ▼
MarketplaceSnapshotComparisonInput
              │
              ▼
PriceChangesModule
              │
              ▼
IntelligenceResult
```

The application service performs one bounded newest-first history query and
supplies at most the newest two snapshots in explicit previous/latest roles.
It does not filter sources or statuses, calculate changes, write history or
format presentation values. The module does not query a repository, select a
different historical pair, read a clock or contact a provider. Neither the
service nor the module runs automatically during startup, Explorer navigation
or tab selection.

### Snapshot comparability

A comparison requires two distinct snapshot identifiers, a previous
`captured_at` strictly earlier than the latest value in absolute time, and the
same stable Marketplace source. The Marketplace History snapshot-ID tie-break
continues to make repository queries deterministic, but it does not make
equal-time snapshots analytically ordered. Different source versions do not by
themselves prevent comparison of canonical domain fields; their difference is
retained as diagnostic evidence.

`COMPLETE`, `PARTIAL` and `EMPTY` snapshots are eligible. A partial input keeps
valid comparisons and source diagnostics and makes the typed comparison
partial. Empty is a valid historical observation: an empty previous snapshot
can establish that a latest observation was newly observed relative to that
pair, while an empty latest snapshot can establish only that a previous
observation is no longer observed in that pair. It does not prove that a
listing is new to the entire Marketplace, sold, withdrawn or expired.

Missing or single-snapshot input produces a skipped result with insufficient
history. An input whose previous capture follows the latest capture is rejected
at construction. Equal capture times remain representable so the module can
return a skipped result with insufficient data; different sources and
unavailable input use the same skipped comparison outcome. Failed input
produces a failed result. None of these outcomes fabricates change records.
Two non-empty snapshots that supply no listing prices and no lowest or highest
release-price facts also produce insufficient data: absence of supported
evidence is not presented as evidence that prices were unchanged. Two explicit
`EMPTY` observations remain a valid no-change comparison.

### Listing price changes

Listing identity is the established `(release_id, listing_id)` pair. Source
order, artist, title, condition, seller region and price are never used to
match identities. For a continuing identity, Price Changes compares the exact
supplied listing price only:

- `increased` means the latest amount is greater in the same currency;
- `decreased` means the latest amount is lower in the same currency;
- `newly_observed` means the identity appears only in the latest supplied
  snapshot;
- `no_longer_observed` means it appears only in the previous supplied snapshot;
- `incomparable` means a continuing listing cannot be compared, including when
  its currencies differ;
- an exact same-currency price is unchanged.

Increased, decreased, newly observed, no-longer-observed and incomparable
records remain in the detailed typed output. Unchanged continuing listings are
omitted from that detail and retained in the summary counts. Incomparable
records are also counted and diagnosed rather than silently discarded.
Shipping, condition and seller-region changes do not drive classification, and
the module never calculates a price-plus-shipping total.

### Release price changes

Release observations align only by `release_id`. This first slice compares the
two supplied monetary fields `lowest_price` and `highest_price`; it does not
compare supply, demand, last-sold dates or status as Price Changes, and it does
not derive release aggregates from listings. Each field independently becomes
increased, decreased, newly available, no longer available, incomparable or
unchanged. Missing money is absence, never zero. Presence on only one side is
described as observation availability relative to the supplied snapshots, not
as a claim that the release entered or left the Marketplace. Unchanged facts
are counted rather than emitted as detailed changes.

Every comparable delta is the signed exact `Decimal` calculation
`latest - previous`. A decrease therefore has a negative delta. Calculation is
permitted only when both values have the same currency; cross-currency records
retain their two values, become incomparable and have no delta. The module does
not convert currencies, use binary floating point, round implicitly or
calculate percentages.

Listing changes have the canonical order:

1. relevant observation time descending, using the latest time for continuing
   and newly observed listings and the previous time for no-longer-observed
   listings;
2. release identifier ascending;
3. listing identifier ascending;
4. stable change-kind order only if another tie remains.

Release changes are ordered by release identifier ascending and then by the
fixed metric order `lowest_price`, `highest_price`. Neither sequence is ranked
by price, delta, desirability or display text.

The module returns the standard `IntelligenceResult` with module ID
`price_changes`, version `1.0`, and an immutable typed output containing narrow
snapshot references, comparison completeness, ordered listing and release
changes, summary counts and diagnostics. A valid comparison with no detailed
changes is completed and empty, not unavailable. Price Changes remains outside
the Version 0.2 default registry because that registry cannot supply its
historical pair without separate application orchestration.

Its presentation service consumes only an already-produced result. The sixth
Collection Explorer destination preserves the domain order and classifications
and performs no history query, comparison, delta calculation, currency
conversion or sorting.

## Marketplace Intelligence foundation exclusions

The Marketplace Intelligence model-and-serialization foundation itself does
not implement data acquisition, API clients, authentication, scheduling,
caching, opportunity scoring, Dashboard presentation, recommendations, buying
or selling automation, or AI-generated summaries. Marketplace History is the
separate repository and SQLite boundary described above. Weekend Listings and
Price Changes are additive intelligence consumers of the models rather than
foundation or persistence responsibilities. Price Changes adds no Marketplace
schema migration and does not change Marketplace serialization schema version
1.

---

# Future Data Providers

Marketplace Architecture should not assume Discogs is the only provider.

Future providers could include:

- eBay;
- Popsike;
- Record Collector;
- user-contributed pricing;
- regional marketplaces.

Provider-specific logic belongs inside the Import Service.

The repository interface should remain unchanged.

---

# Versioning

Marketplace models should evolve without breaking existing snapshots.

New fields should be additive wherever practical.

Historic snapshots should remain valid.

---

# Error Handling

Marketplace failures should not prevent Collection Intelligence from executing.

Example:

```text
Collection Health

Completed

Hidden Gems

Completed

Marketplace Trends

Skipped
```

The platform should continue producing partial intelligence whenever possible.

---

# Database Design

The implemented aggregate history schema is intentionally compact:

```text
marketplace_snapshots
├── snapshot_id
├── captured_at
├── source
├── status
├── schema_version
└── payload_json
```

`payload_json` contains the complete canonical aggregate, including exact money,
release observations and listing observations. The existing legacy
`market_snapshots` release table remains separate and unchanged; it is not the
Marketplace History contract.

Future tables may include:

- marketplace providers;
- cached exchange rates;
- import history.

The initial schema should remain intentionally small.

---

# Architectural Constraints

Marketplace Architecture must:

- isolate external APIs;
- remain deterministic;
- preserve history;
- support offline execution;
- remain presentation-independent;
- expose repository interfaces;
- support future providers;
- integrate through IntelligenceContext;
- return IntelligenceResult;
- avoid direct UI dependencies.

---

# Future Extensions

Potential future capabilities include:

- Marketplace Alerts;
- Opportunity Engine;
- comparable release analysis;
- artist popularity forecasting;
- regional pricing;
- currency normalisation;
- volatility indicators;
- liquidity analysis;
- marketplace confidence scoring;
- cross-provider aggregation.

These should extend the architecture rather than replacing it.

---

# Summary

Marketplace Architecture provides the reusable foundation for all future Marketplace Intelligence.

It separates:

- acquisition;
- storage;
- access;
- intelligence;
- presentation.

Marketplace snapshots preserve what happened in the marketplace.

Marketplace Intelligence explains what those observations mean.

Together with Collection History and Intelligence History, Marketplace Architecture completes the three historical pillars of the Discogs Intelligence Platform:

- Collection History
- Intelligence History
- Marketplace History

These foundations enable transparent, explainable and evidence-based intelligence while remaining faithful to DIP's guiding principle:

> **Automate the research, not the collecting decision.**
