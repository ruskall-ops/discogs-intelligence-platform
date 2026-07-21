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
schema or migration is introduced by this foundation.

---

# Marketplace Repository

Marketplace data should only be accessed through a repository.

Suggested interface:

```python
class MarketplaceRepository(Protocol):

    def latest_snapshot(
        self,
        release_id: int,
    ) -> MarketplaceSnapshot | None:
        ...

    def historical_snapshots(
        self,
        release_id: int,
    ) -> tuple[MarketplaceSnapshot, ...]:
        ...

    def save_snapshot(
        self,
        snapshot: MarketplaceSnapshot,
    ) -> None:
        ...
```

Intelligence modules should never know whether data originated from:

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

No additional presentation logic is required.

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

The foundation is history-ready but not history-integrated. Its serialization
does not write Intelligence History and this slice does not change history
models, repositories or formats. A future application boundary may persist raw
Marketplace snapshots in a peer Marketplace History store and preserve the
standard result through Intelligence History without changing either meaning.

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

The first slice deliberately excludes Marketplace fetching and persistence,
monitoring, scheduling, scoring, recommendations, user sorting, and filtering.
Its Explorer presentation consumes an already-produced result and never runs
the module on navigation.

## Foundation exclusions

The Marketplace foundation itself does not implement data acquisition, API
clients, authentication, repositories, SQLite, migrations, scheduling, caching,
price-change detection, opportunity scoring, Dashboard presentation,
recommendations, buying or selling automation, or AI-generated summaries.
Weekend Listings is an additive consumer of the foundation rather than a
foundation responsibility.

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

Conceptually:

```text
marketplace_snapshots

release_id

captured_at

lowest_price

median_price

highest_price

num_for_sale

num_wanted

last_sold

currency
```

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
