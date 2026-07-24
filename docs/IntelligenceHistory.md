# Intelligence History

## Purpose

Intelligence History defines how the Discogs Intelligence Platform (DIP) preserves the output of every Intelligence Engine execution.

Unlike Collection History, which records changes to the user's collection, Intelligence History records how the platform's **conclusions** evolve over time.

It provides a permanent historical record of every intelligence execution, enabling future analysis of changing insights, methodology improvements, and long-term intelligence trends.

Examples include:

- Has Collection Health improved?
- When did Hidden Gems first appear?
- Which releases stopped being Hidden Gems?
- Has marketplace demand continued to increase?
- Did a methodology change alter historical results?

Intelligence History provides the foundation for answering these questions.

It is intentionally independent of presentation, storage technology and user interface.

---

# Philosophy

The Intelligence Engine should behave like a scientist.

Every execution represents an observation made using the best information available at that point in time.

Those observations should never be discarded.

Historical intelligence should therefore be immutable.

The platform should be capable of explaining not only:

> "What is the current intelligence?"

but also:

> "What did we believe yesterday?"

and

> "Why has that conclusion changed?"

History creates explainability.

---

# Core Principle

Every execution of the Intelligence Engine creates one immutable historical record.

Nothing is overwritten.

Historical records represent exactly what the engine concluded when that execution completed.

Conceptually:

```text
IntelligenceContext
        │
        ▼
Intelligence Engine
        │
        ▼
Intelligence Execution
        │
        ▼
Intelligence History
```

Future executions create additional history.

```text
Execution 1

↓

Execution 2

↓

Execution 3

↓

Execution 4
```

The historical timeline grows indefinitely.

---

# Relationship to Other Historical Systems

DIP eventually contains three complementary historical systems.

## Collection History

Records:

- releases added
- releases removed
- collection statistics
- ownership history

Collection History answers:

> What changed in the collection?

---

## Marketplace History

Records:

- prices
- demand
- supply
- marketplace activity

Marketplace History answers:

> What changed in the marketplace?

---

## Intelligence History

Records:

- module conclusions
- scores
- evidence
- diagnostics
- insights

Intelligence History answers:

> What did the platform conclude?

These systems solve different problems.

They should remain independent.

---

# Design Goals

The architecture should:

- preserve every Intelligence Engine execution;
- never overwrite historical intelligence;
- remain deterministic;
- remain presentation-independent;
- support future comparison features;
- support future Marketplace Intelligence;
- preserve methodology versions;
- support reproducible historical analysis;
- remain independent of storage technology;
- integrate naturally with the existing Intelligence Engine.

---

# Guiding Principles

## Intelligence is immutable

Historical conclusions should never change.

If an intelligence module is improved, a **new execution** is created.

Old executions remain unchanged.

---

## Intelligence is reproducible

Given:

- the same collection snapshot;
- the same marketplace snapshot;
- the same engine version;

the Intelligence Engine should produce identical results.

History exists to preserve those results.

---

## Intelligence is explainable

Every historical record should preserve:

- summary
- evidence
- diagnostics
- metrics
- status

Nothing should be reduced to an opaque score.

---

# Existing Intelligence Contract

The current Collection Intelligence architecture already produces immutable IntelligenceResult objects.

Intelligence History should build directly upon this existing contract.

It should **not** introduce a second result hierarchy.

Instead:

```text
Intelligence Module

↓

IntelligenceResult

↓

Intelligence History
```

The historical layer stores existing IntelligenceResult data.

Presentation remains elsewhere.

---

# Historical Execution

Every execution creates exactly one historical run.

A run represents:

- one execution;
- one point in time;
- one engine version;
- one collection context.

It is the parent object for every module result generated during that execution.

Suggested model:

```python
@dataclass(frozen=True)
class IntelligenceHistoryRun:
    run_id: int | None
    executed_at: datetime
    engine_version: str | None = None
    collection_snapshot_id: int | None = None
    result_count: int = 0
```

The collection snapshot reference is optional.

Future executions may originate from sources other than collection snapshots.

---

# Historical Result Records

Each IntelligenceResult produced during execution becomes one historical record.

Suggested model:

```python
@dataclass(frozen=True)
class IntelligenceHistoryRecord:
    record_id: int | None
    run_id: int
    module_id: str
    module_version: str | None
    status: IntelligenceStatus
    summary: str
    insights: tuple[str, ...]
    metrics: Mapping[str, Any]
    evidence: tuple[str, ...]
    diagnostics: tuple[str, ...]
```

The existing `IntelligenceStatus` type should always be reused.

No duplicate status enum should be introduced.

---

# Why Separate Runs and Records?

Separating executions from module results provides a simple one-to-many relationship.

```text
Run
 │
 ├── Collection Health
 ├── Hidden Gems
 ├── Historical Intelligence
 ├── Marketplace Trends
 └── Future Modules
```

This allows modules to evolve independently while preserving the context of the overall execution.

# Serialization

## Purpose

Intelligence History must preserve historical records in a deterministic, portable and implementation-independent format.

Serialization should produce identical output whenever the same intelligence result is serialized.

This guarantees:

- reproducible persistence;
- deterministic testing;
- stable historical comparisons;
- future migration compatibility.

Serialization is part of the Intelligence History foundation rather than the persistence layer.

---

# Supported Value Types

Historical records may contain:

- None
- bool
- int
- finite float
- str
- list
- tuple
- mappings with string keys
- date
- datetime
- Decimal
- timedelta
- Enum
- approved immutable dataclasses

Any unsupported value must fail immediately.

Silent conversion is not permitted.

---

# Unsupported Values

Examples include:

- arbitrary Python objects;
- file handles;
- functions;
- generators;
- sets;
- complex numbers;
- bytes;
- NaN;
- positive infinity;
- negative infinity.

Attempting to serialize unsupported values should raise an explicit IntelligenceSerializationError.

---

# Why Explicit Serialization?

Python's default JSON behaviour is intentionally avoided.

For example:

```python
json.dumps(value, default=str)
```

is prohibited.

Although convenient, it destroys type information and allows ambiguous representations.

Historical intelligence should preserve meaning rather than simply producing valid JSON.

---

# Tagged Values

Certain Python types cannot safely be represented as ordinary JSON.

For example:

```python
date(2026, 7, 21)
```

should not become:

```json
"2026-07-21"
```

because this becomes indistinguishable from an ordinary string.

Instead, tagged values should be used.

Example:

```json
{
    "__dip_type__": "date",
    "value": "2026-07-21"
}
```

The exact tag naming may evolve, but the representation must remain explicit.

---

# Tuples

Lists and tuples have different semantic meaning.

For example:

```python
[
    "A",
    "B"
]
```

is mutable.

Whereas:

```python
(
    "A",
    "B",
)
```

represents an immutable ordered collection.

Historical serialization should preserve this distinction.

---

# Datetimes

Datetimes should always use ISO-8601 format.

Timezone information should be preserved where available.

Naive datetimes should remain naive.

Datetime serialization should never depend upon the local machine locale.

For repository ordering, naive execution datetimes are treated as UTC. This
normalisation affects only the deterministic ordering key; the original naive
datetime remains preserved in its serialized form.

---

# Dates

Dates should remain dates.

Do not convert dates into datetimes.

---

# Enumerations

Enumerations should be serialized explicitly.

Historical records should preserve:

- enumeration type;
- enumeration value.

This allows future versions of DIP to interpret historical values safely without requiring arbitrary imports.

---

# Immutable Dataclasses

Approved immutable dataclasses may be serialized.

Approval should be explicit.

Merely being frozen should not automatically qualify every dataclass for serialization.

Future versions may maintain an explicit registry of supported dataclasses.

---

# Mapping Rules

Mappings must satisfy:

- string keys only;
- deterministic ordering;
- recursively serializable values.

Non-string keys should raise an explicit serialization error.

---

# Deterministic JSON

The public JSON representation should always use:

- sorted keys;
- compact separators;
- UTF-8;
- deterministic ordering.

The same logical object should always generate identical JSON.

---

# Public Serialization API

Suggested public interface:

```python
serialize_intelligence_value(
    value: Any,
) -> JsonValue

deserialize_intelligence_value(
    value: JsonValue,
) -> Any

dumps_intelligence_value(
    value: Any,
) -> str

loads_intelligence_value(
    payload: str,
) -> Any
```

Helper functions should remain internal.

Only the public API should be exported.

---

# Deserialization

Deserialization should perform strict validation.

Malformed tagged values should fail immediately.

Examples include:

- missing required fields;
- unknown tag types;
- invalid ISO dates;
- invalid datetimes;
- malformed enums.

Historical data should never silently recover from corruption.

---

# Error Reporting

Serialization errors should identify:

- unsupported type;
- offending field;
- nested location where possible.

For example:

```text
metrics.price_history[4]
```

provides significantly better diagnostics than:

```text
Unsupported type.
```

---

# Repository Boundary

Intelligence History does not define storage.

Instead it defines the repository contract.

Suggested interface:

```python
class IntelligenceHistoryRepository(Protocol):

    def save_execution(...):
        ...

    def latest_run(...):
        ...

    def latest_result(...):
        ...

    def previous_result(...):
        ...

    def history_for_module(...):
        ...
```

Persistence technology remains an implementation detail.

---

# Repository Responsibilities

The repository owns:

- persistence;
- retrieval;
- ordering;
- transactions.

The repository does **not**:

- calculate intelligence;
- compare intelligence;
- create Dashboard models;
- create Explorer models.

---

# SQLite Persistence

SQLite is the initial persistence technology.

The architecture intentionally avoids coupling itself to SQLite.

Alternative implementations should remain possible.

---

# Database Design

Conceptually the schema consists of two tables.

## intelligence_runs

Stores execution-level metadata.

Suggested columns:

- id
- executed_at
- engine_version
- collection_snapshot_id
- result_count

---

## intelligence_results

Stores one row per module result.

Suggested columns:

- id
- run_id
- module_id
- module_version
- status
- summary
- insights_json
- metrics_json
- evidence_json
- diagnostics_json

Relationships remain one-to-many.

---

# Indexing

The implementation should support efficient lookup by:

- execution date;
- module;
- run identifier.

This enables future comparison features without redesigning the schema.

---

# Migration Philosophy

Historical data should be additive.

Future schema evolution should preserve historical records wherever practical.

Existing executions should remain readable after migrations.

# Execution Lifecycle

## Overview

Intelligence History is not responsible for executing intelligence modules.

Its responsibility begins only after an Intelligence Engine execution has completed.

Conceptually:

```text
Intelligence Context
        │
        ▼
Intelligence Engine
        │
        ▼
Collection of IntelligenceResult objects
        │
        ▼
Intelligence History
```

This separation ensures the Intelligence Engine remains deterministic and free from persistence concerns.

---

# Application Service

Persistence should occur through an application service rather than inside the Intelligence Engine.

Conceptually:

```text
Intelligence Context
        │
        ▼
Intelligence Engine
        │
        ▼
IntelligenceExecutionService
        │
        ▼
Intelligence History Repository
```

The Intelligence Engine produces intelligence.

The application service decides whether and how that intelligence should be persisted.

The Collection Intelligence execution service is the orchestration boundary for
the current implementation. It executes the engine, verifies that every
registered module completed, converts results into immutable history records,
and asks the repository to save the complete execution atomically.

Records preserve the Intelligence Engine's registry order. The registry already
provides deterministic, unique module registration, so no presentation label or
unordered collection is used to determine historical ordering.

An execution with no registered modules is a valid observation and produces a
run with `result_count=0`.

---

# Why Separate Persistence?

Embedding persistence directly inside the engine would tightly couple intelligence generation to storage technology.

Instead:

- the Intelligence Engine remains pure;
- Intelligence History becomes optional;
- testing becomes simpler;
- future storage implementations remain possible.

---

# Execution Flow

The expected execution flow is:

```text
Build IntelligenceContext

↓

Execute Intelligence Engine

↓

Receive IntelligenceResult collection

↓

Create IntelligenceHistoryRun

↓

Create IntelligenceHistoryRecord objects

↓

Persist atomically

↓

Return IntelligenceResult collection
```

On success, the caller receives the original `IntelligenceExecution` together
with the persisted `IntelligenceHistoryRun`. A persistence failure is propagated
and no successful orchestrated result is returned.

---

# Transaction Boundaries

One engine execution represents one transaction.

Conceptually:

```text
Begin Transaction

↓

Insert IntelligenceHistoryRun

↓

Insert HistoryRecord 1

↓

Insert HistoryRecord 2

↓

Insert HistoryRecord N

↓

Commit
```

Either the entire execution is persisted or none of it is.

Partial executions should never exist.

---

# Rollback Behaviour

If persistence fails during an execution:

- all inserted records are rolled back;
- no partial history remains;
- the Intelligence Engine result remains valid.

History should never contain incomplete executions.

---

# Failure Behaviour

The following are different failures:

## Module failure

Example:

```text
Collection Health

Completed

Marketplace Trends

Failed
```

This is a valid engine result, but it is not persisted by the current Collection
Intelligence orchestration slice. History is written only when every intended
module has status `Completed`; failed or skipped executions remain visible to
the caller and create no historical run.

---

## Persistence failure

Example:

```text
History database unavailable
```

The intelligence execution succeeded.

Only historical recording failed.

These should not be treated as the same failure.

The application service surfaces the persistence error without rerunning the
engine. Repository transaction guarantees ensure no partial execution remains.

---

# Status Preservation

Historical records should preserve the exact module status returned by the Intelligence Engine.

Examples include:

- Completed
- Skipped
- Unavailable
- Failed

No historical reinterpretation should occur.

---

# Version Preservation

Every execution should preserve:

- engine version;
- module version.

Historical records should always be interpreted using the methodology that produced them.

Future algorithm improvements should create new executions rather than modifying previous records.

---

# Methodology Changes

Suppose Hidden Gems changes its scoring algorithm.

Old executions should remain unchanged.

Future executions automatically use the new methodology.

Historical comparisons can then explain:

- score changes caused by market movement;
- score changes caused by methodology changes.

---

# Historical Retrieval

The repository should support retrieval of:

## Latest execution

```text
Most recent run.
```

---

## Previous execution

```text
Execution immediately preceding the latest.
```

---

## Module history

Example:

```text
Collection Health

↓

Run 1

↓

Run 2

↓

Run 3

↓

Run 4
```

This forms the basis for trend visualisation.

---

## Chronological history

Retrieve every execution ordered by execution date.

This supports future reporting and diagnostics.

---

# Read-Only Application Queries

Historical data is exposed to future Dashboard, Explorer and comparison callers
through `IntelligenceHistoryQueryService`. The service depends only on the
`IntelligenceHistoryRepository` protocol and contains no SQLite, presentation,
comparison or write behaviour.

The public query boundary provides:

- the latest complete execution;
- the previous complete execution;
- one complete execution by persisted run identifier;
- a limited sequence of recent complete executions;
- module-specific history with parent-run context;
- the latest and previous result for one module.

A complete execution contains its `IntelligenceHistoryRun` and every associated
`IntelligenceHistoryRecord`. Records remain in their deterministic persisted
order, which is the engine registry order established when the execution was
saved.

Execution queries are newest first by:

```text
executed_at DESC

run_id DESC
```

Module history is also returned newest first using the parent run's execution
timestamp and run identifier. “Previous module result” is module-specific, so a
global run that did not contain that module does not interrupt its history.

Absence is represented consistently:

- singular queries return `None`;
- plural queries return an empty immutable tuple.

Public identifiers and limits are validated before repository access. A
historical execution is rejected as inconsistent when its declared result count
does not match its records, a record belongs to another run, a module occurs
more than once, or a module record references a missing run. Stored counts are
never silently adjusted and partial executions are never returned.

The first implementation deliberately composes narrow repository reads. Recent
execution retrieval performs one limited run query followed by one ordered
record query for each selected run; module history resolves each selected
record's parent run. This keeps the repository contract focused and the recent
query cost bounded by the caller's positive limit. A batch read may replace this
strategy later if measured history volumes justify the additional contract.

---

# Comparison Philosophy

History stores observations.

Comparison interprets observations.

For example:

History stores:

```text
Collection Health

82

↓

84

↓

87
```

Comparison explains:

```text
+5 points

Demand increased

Duplicates reduced

Median value improved
```

These responsibilities remain separate.

---

# Comparison Engine Foundation

The Comparison Engine is a deterministic, storage-independent domain service.
It compares two complete `HistoricalIntelligenceExecution` values that have
already been assembled by the read-only Intelligence History query boundary.
It never queries SQLite, calculates new intelligence, or creates presentation
models.

Conceptually:

```text
IntelligenceHistoryQueryService
            │
            ▼
IntelligenceComparisonService
            │
            ▼
      ComparisonEngine
            │
            ▼
     ComparisonRegistry
            │
            ▼
       ModuleComparer
```

The engine validates both historical executions, aligns their module IDs, and
dispatches each module to its registered comparer. Module-specific comparison
logic belongs in comparer plugins rather than the engine.

The default registry explicitly registers generic comparers for the current
Collection Intelligence modules. An unregistered future module receives a
stateless generic comparer without mutating registry order. Specialised
comparers may replace generic registrations in future slices.

The generic comparer reports structural `ValueChange` values for:

- status;
- summary;
- metrics;
- evidence;
- diagnostics.

Each value exposes its previous value, current value and deterministic `changed`
boolean. Equality uses the canonical type-preserving Intelligence History
representation, so values such as `true`, `1`, and `1.0` remain distinct. The
generic comparer does not calculate scores, metric deltas, trends, or
natural-language explanations.

Every module in either execution produces one immutable `ModuleComparison`.
Modules found only in the current execution are marked `added`; modules found
only in the previous execution are marked `removed`. Shared modules are marked
`changed` or `unchanged` from their structural field comparisons.

Module ordering follows the current execution's persisted engine-registry order.
Removed modules, which have no current position, follow afterward in their
previous persisted order. No alphabetical or database-dependent ordering is
introduced.

The application service supports comparing the latest two executions, two
already loaded executions, or two persisted run identifiers. Empty or
single-execution history cannot produce a latest comparison and raises an
explicit availability error. Missing run identifiers also raise an explicit
not-found error.

---

# Comparison ViewModel Boundary

Structured `ExecutionComparison` results are transformed for future interfaces
through the presentation-neutral Comparison ViewModel boundary under
`dip.experience.comparison`.

Conceptually:

```text
IntelligenceComparisonService
            │
            ▼
ComparisonPresentationService
            │
            ▼
ComparisonViewModelBuilder
            │
            ▼
ExecutionComparisonViewModel
            │
      ┌─────┴─────┐
      ▼           ▼
Dashboard       Explorer
 future         future
```

The builder receives an already calculated comparison. It performs no history
queries, persistence access, comparison calculation, scoring, or domain
interpretation. Dashboard and Explorer components are not part of this slice.

The immutable ViewModels expose execution-level state counts, module-level
change classifications, and the five generic field changes. Canonical IDs are
preserved separately from stable presentation labels. Known module and field
labels use explicit immutable mappings; unknown module IDs receive a
deterministic snake-case-to-title-case fallback.

Module ordering remains exactly as supplied by `ExecutionComparison`. Generic
fields use the explicit order: status, summary, metrics, evidence, diagnostics.
Neither sequence is sorted by its display label.

Each field records previous and current availability independently. An
unavailable side is therefore distinct from an available comparison value whose
legitimate value is `None`. Structured typed values remain immutable and are not
flattened into display strings.

Contradictory comparison states, duplicate modules or fields, malformed added
or removed modules, and inconsistent summary counts raise an explicit
`ComparisonViewModelConsistencyError`; the builder does not silently repair
them. `ComparisonPresentationService` composes the existing comparison service
with the builder and does not swallow failures from either dependency.

---

# Why Generic Storage?

The repository intentionally stores generic IntelligenceResult information.

It does not understand:

- Collection Health
- Hidden Gems
- Marketplace Trends

Those meanings belong to the individual modules.

This allows future modules to participate automatically in Intelligence History without requiring repository changes.

---

# Duplicate Executions

Repeated executions are valid.

For example:

```text
09:00

↓

09:05

↓

09:10
```

All three executions should be preserved.

The repository should not attempt to detect or remove duplicates.

Determining whether two executions are "equivalent" is a business concern rather than a persistence concern.

---

# Relationship with Collection History

Collection History and Intelligence History should remain loosely coupled.

A historical run may optionally reference the collection snapshot that generated it.

```text
Collection Snapshot

↓

Intelligence Execution

↓

History Run
```

However, neither system should require the other to function.

The application service populates `collection_snapshot_id` only when the caller
already has a valid collection snapshot identifier. It does not infer one from
marketplace analysis runs or create Collection History solely for linkage.

---

# Relationship with Marketplace History

Marketplace History is now a separate append-only repository boundary for raw,
canonical `MarketplaceSnapshot` observations. It does not place complete raw
listings, release observations or snapshot payloads inside Intelligence History
records. A module result may retain only the narrow typed evidence and
diagnostics required to explain its derived conclusion.

Marketplace Intelligence may participate in Intelligence History through the
existing standard result contract:

Conceptually:

```text
Marketplace Snapshot

↓

Marketplace Intelligence Module

↓

IntelligenceResult

↓

Intelligence History
```

No special Intelligence History repository behaviour is required. Marketplace
History preserves what the source reported; Intelligence History preserves
what a versioned module concluded from supplied evidence. Links between those
observations may be introduced by future orchestration without conflating the
two stores.

Marketplace Intelligence should integrate naturally through the existing IntelligenceResult contract.

Price Changes follows this boundary. Marketplace History retains the two full
raw snapshots, while the `price_changes` result retains narrow snapshot
references, typed factual listing and release-price changes, summary counts and
diagnostics. It does not copy either complete snapshot into an Intelligence
History record. Historical snapshot selection remains application
orchestration; neither Intelligence History nor its repository selects or
recalculates the comparison.

The frozen Price Changes output, snapshot reference, listing-change,
release-change and signed-delta value types, together with their stable enums,
are explicit additions to the deterministic Intelligence History allow-list.
They use the existing approved-dataclass and enum tags. This is an additive type
registration only: the Intelligence History wire format, repository contract
and SQLite schema are unchanged, as is Marketplace serialization schema
version 1. Unknown dataclasses, enums and tagged values remain rejected.

---

# Architectural Responsibility

The Intelligence Engine owns:

- calculation;
- evidence generation;
- diagnostics;
- scoring.

The Intelligence History layer owns:

- preservation;
- retrieval;
- chronology;
- persistence.

Keeping these responsibilities separate keeps the architecture modular and easier to evolve.

---

# Design Summary

The execution lifecycle is intentionally simple:

```text
Execute Intelligence

↓

Collect Results

↓

Persist Results

↓

Return Results
```

History should never influence the intelligence being produced.

It merely records what the platform concluded at that moment in time.


# Testing Strategy

The Intelligence History foundation should be fully testable without requiring SQLite, the Dashboard, or any user interface components.

Testing should focus on deterministic behaviour, immutability and architectural boundaries.

---

# Model Tests

Domain models should verify:

- immutability;
- equality behaviour;
- optional fields;
- defensive handling of mutable inputs;
- deterministic construction.

Tests should confirm that historical records cannot be modified after creation.

---

# Serialization Tests

Serialization is a critical component of the architecture.

Tests should verify:

## Primitive Values

- None
- bool
- int
- float
- str

---

## Collections

- lists
- tuples
- nested collections
- nested mappings

---

## Dates

- date
- datetime
- timezone-aware datetime
- naive datetime

---

## Enumerations

Verify that:

- values serialize correctly;
- deserialization restores the correct enum;
- invalid enum values raise explicit errors.

---

## Dataclasses

Approved immutable dataclasses should:

- serialize deterministically;
- deserialize correctly;
- reject unsupported dataclasses.

---

## Invalid Values

Tests should confirm failures for:

- NaN
- Infinity
- complex numbers
- sets
- bytes
- arbitrary Python objects
- functions
- generators

Silent conversion should never occur.

---

## Deterministic Output

Repeated serialization of identical objects should produce byte-for-byte identical JSON.

Ordering must never depend upon:

- dictionary insertion order;
- operating system;
- Python runtime.

---

# Repository Tests

Repository implementations should verify:

- successful execution persistence;
- retrieval ordering;
- latest execution lookup;
- previous execution lookup;
- module history retrieval;
- transaction rollback;
- empty repository behaviour.

The repository should remain entirely deterministic.

---

# Architectural Tests

Architecture tests should confirm:

- the Intelligence Engine contains no persistence logic;
- serialization is independent of SQLite;
- repositories remain independent of presentation;
- Dashboard code does not reference persistence;
- Explorer code does not reference persistence.

These tests protect long-term architectural integrity.

---

# Acceptance Criteria

The Intelligence History foundation is considered complete when it supports:

- immutable execution runs;
- immutable historical records;
- deterministic serialization;
- explicit deserialization;
- repository abstraction;
- transaction-ready persistence;
- historical chronology;
- module version preservation;
- optional collection snapshot linkage;
- deterministic unit tests.

The implementation should be capable of supporting future intelligence modules without architectural changes.

---

# Future Extensions

The foundation intentionally enables future capabilities without requiring redesign.

Examples include:

## Historical Comparison Engine

Compare any two executions.

Examples:

- score movement;
- new insights;
- removed insights;
- changing diagnostics;
- changing evidence.

---

## Trend Analysis

Historical module trends may be visualised.

Examples:

```text
Collection Health

82

↓

84

↓

87

↓

91
```

or

```text
Hidden Gems

5

↓

7

↓

11

↓

13
```

Trend analysis belongs above the repository layer.

## First Collection Trends presentation

The first read-only Collection Trends experience queries at most the latest
five complete historical executions through `IntelligenceHistoryQueryService`
and selects the newest two containing a completed or skipped module result.
It compares only that two-execution window; it does not claim a long-term
trend, forecast, or recommendation.

The existing Comparison Engine supplies deterministic run and module alignment.
The Trends presentation projects persisted collection-level values into typed,
neutral absolute changes. It never queries SQLite directly, writes history, or
executes intelligence. The Collection Explorer performs the query once while
building its workspace; selecting the Trends tab performs no additional query.

---

## Methodology Evolution

Historical records preserve module versions.

Future tools can distinguish between:

- genuine market changes;
- improvements to intelligence methodology.

This improves transparency and explainability.

---

## Performance Monitoring

Historical executions may later record:

- execution duration;
- module timings;
- cache utilisation;
- diagnostic statistics.

These metrics should remain optional and should not complicate the core historical model.

---

## Marketplace Intelligence

Marketplace Intelligence module results integrate through the standard result
contract without a repository redesign. Weekend Listings and Price Changes
typed outputs use explicit deterministic type registrations; registration does
not make either module execute or persist automatically.

Because Intelligence History stores generic `IntelligenceResult` objects,
future modules require no repository redesign when their complex immutable
values are deliberately added to the serialization allow-list.

The architecture remains open for extension but closed for modification.

---

## Dashboard Integration

Dashboard widgets should consume Intelligence History through application services.

They should never query persistence directly.

This preserves separation between:

- domain;
- persistence;
- presentation.

---

# Architectural Constraints

The following constraints should remain true throughout the lifetime of the project.

The implementation must:

- remain deterministic;
- remain immutable;
- remain presentation-independent;
- preserve every execution;
- never overwrite historical records;
- reuse the existing `IntelligenceResult` contract;
- reuse the existing `IntelligenceStatus` enumeration;
- isolate persistence behind repository interfaces;
- support future intelligence modules without redesign;
- remain independent of SQLite-specific behaviour wherever practical.

Whenever new functionality is proposed, these principles should take precedence over implementation convenience.

---

# Relationship to the Discogs Intelligence Platform

Intelligence History forms one of the foundational architectural layers of DIP.

Together with Collection History and Marketplace History it creates a complete historical model of the platform.

```text
Collection History
        │
        ├── What changed?
        │
Marketplace History
        │
        ├── What happened?
        │
Intelligence History
        │
        └── What did the platform conclude?
```

These three histories complement one another while remaining independently maintainable.

---

# Relationship to Collection Intelligence

Collection Intelligence Modules
           │
           ▼
    IntelligenceResult
           │
           ▼
 Intelligence History
           │
           ▼
  Future Comparison Engine
           │
           ▼
 Dashboard / Explorer


# Summary

The purpose of Intelligence History is not simply to archive data.

Its purpose is to preserve knowledge.

Every execution of the Intelligence Engine represents an observation made using a specific collection, a specific marketplace state and a specific methodology.

Those observations become part of the permanent historical record.

By preserving them immutably, DIP gains the ability to explain not only its current recommendations, but how those recommendations have evolved over time.

This capability underpins future features including trend analysis, historical comparisons, explainable intelligence and methodology evolution.

The architecture deliberately separates intelligence generation from intelligence preservation.

The Intelligence Engine calculates.

The History layer remembers.

The Comparison layer interprets.

The Dashboard presents.

Maintaining these responsibilities as separate concerns keeps the platform deterministic, testable and extensible.

Ultimately, Intelligence History embodies the core philosophy of the Discogs Intelligence Platform:

> **Automate the research, not the collecting decision.**
## Historical Intelligence: Change Analysis 1.0

Intelligence Change Analysis is the first Historical Intelligence capability.
It compares exactly two explicitly supplied immutable `IntelligenceResult`
snapshots. Version 1 supports only `portfolio_opportunity_alignment` module
version and rule set `1.0`.

It validates typed outputs, completed status, identities, versions, rule sets,
and available snapshot provenance. Invalid or unsupported inputs produce a
deterministic insufficient result. Transitions preserve previous and current
assessment, evidence, versions, reasons, diagnostics, provenance, dimensions,
release/copy counts, and exact Decimal ratios. Numeric differences are
`increased`, `decreased`, or `unchanged`; categorical differences are
`modified`, never improvements or regressions.

Change Analysis performs no history loading, repository query, provider
execution, recalculation, clock access, or fallback. Its output participates
through additive history serialization registrations. Trend and Evolution
Analysis, automatic retrieval, History Explorer, alerts, and dashboard
integration remain future work.
