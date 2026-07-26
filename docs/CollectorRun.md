# Collector Run

## Purpose

Collector Run is the application boundary for recurring collector workflows
over the collection already stored in SQLite. Version 0.5.1 established the
Discogs Marketplace refresh stage; Version 0.5.2 adds canonical Marketplace
capture to that same application lifecycle. Version 0.5.3 adds coherent
Collection Intelligence execution and Intelligence History recording.

Discogs CSV import remains a separate, explicit, optional collection-update
action. Refreshing Marketplace facts does not require selecting or re-importing
a CSV.

## Implemented boundary

```text
Tkinter desktop
      ↓ temporary token and progress callback
CollectorRunService
      ├── stored collection and legacy persistence boundary
      ├── lazy Discogs provider factory
      ├── pure canonical Marketplace mapper
      ├── Marketplace History command boundary
      ├── explicit canonical Intelligence context factory
      ├── Collection Intelligence execution boundary
      ├── Intelligence History repository boundary
      ├── existing legacy score calculator
      ├── analysis-run lifecycle
      └── immutable progress and result models
```

The desktop prompts for the temporary token, prevents concurrent runs, invokes
the synchronous service on a daemon worker thread, and schedules all display
updates back through Tkinter. It does not coordinate individual releases,
persist snapshots or scores, control the analysis-run lifecycle, or throttle
requests.

`CollectorRunService` is application orchestration. It depends on narrow
structural protocols and callables and imports neither Tkinter nor SQLite. The
composition root supplies the shared `Database`, packaged `DiscogsClient`,
existing Marketplace History command service, score function, application
version, configured delay, UTC clock, and wait function. Provider construction
remains lazy and occurs only for a non-empty stored collection when `run()` is
called.

## Lifecycle

One run:

1. validates the temporary token and ordered stored release identities;
2. rejects an empty collection before provider construction or mutation;
3. lazily creates the provider;
4. obtains one timezone-aware capture timestamp;
5. starts one legacy `market_refresh` `analysis_runs` record;
6. emits initial progress;
7. processes every release in repository-supplied order;
8. appends the legacy per-release observation, calculates the existing score,
   and upserts that current score after a successful provider response;
9. emits progress after every attempt and waits only between attempts;
10. constructs and atomically records one canonical aggregate Marketplace
    snapshot after every attempt lifecycle has finished;
11. for complete or partial evidence, constructs the explicit context, executes
    the Version 0.2 registry, and atomically records completed and legitimately
    skipped module results;
12. completes or fails the parent legacy analysis run and returns an immutable
    terminal result.

The capture timestamp is reused for every observation and score in the run.
Release order, failed release identities, and progress order are deterministic.
Malformed, duplicate, boolean, or non-positive release identities are rejected
before the analysis run starts.

The canonical snapshot uses `collector-run-{analysis_run_id}` identity,
`source="discogs"`, no source version, empty listing observations, and the same
aware run timestamp for the aggregate and every release observation. The
requested release ID is authoritative. Exact provider prices reach canonical
`MarketplaceMoney` as `Decimal`; absence remains absent. A separate pure legacy
projection supplies the existing zero and empty-string defaults and converts
valid exact price to `float` only for legacy persistence and scoring.

Canonical status describes source evidence independently of the legacy
Collector Run result. All complete releases produce `complete`; incomplete or
empty successful observations, or mixed provider outcomes, produce `partial`;
zero provider successes produce `failed`. Provider exceptions, unavailable
observations, missing facts, and unusable money use fixed provider-neutral
diagnostics containing no token, response body, or exception message. A legacy
completed run may therefore record a partial canonical snapshot when every
provider call returned but some canonical facts were incomplete.

## Outcomes

- **Completed:** every release operation succeeded. The legacy analysis run is
  completed with exact counts.
- **Partial:** at least one release succeeded and at least one provider call
  failed or returned no release. The legacy analysis run is completed with
  exact counts and the ordered failed release identities are returned.
- **Failed:** provider processing reached every release but none succeeded. The
  legacy analysis run is marked failed with a safe generic explanation.

Only a provider-call exception or `None` provider response is a recoverable
release failure. Persistence errors, score defects, invalid internal state,
clock failures, and progress-callback failures are not hidden as release
failures.

If a fatal error occurs after the analysis run starts, the service attempts to
mark the run failed with the counts reached so far and raises
`CollectorRunExecutionError` from the original cause. The persisted error is
generic and never contains the Discogs token.

Fatal provider-construction or analysis-run start failures also raise the same
safe application error, with no analysis-run identity and no cleanup attempt,
because no valid active run exists.

Network calls cannot participate in one SQLite transaction. Successful raw
legacy observations written before a later fatal failure may therefore remain
as historical evidence. Their parent analysis run is failed and is excluded
from completed-run queries. This is deliberate.

Canonical construction and recording occur only after all provider attempts,
successful legacy observations and scores, and final progress emission.
Interrupted loops create no canonical snapshot. Canonical mapping or recording
failure is fatal and leaves earlier legacy evidence intact; the canonical
repository itself stores the aggregate atomically or not at all. If canonical
recording succeeds but the legacy terminal write then fails, the immutable
canonical evidence remains. Its ID preserves conventional provenance to the
legacy run without a relational foreign key.

## Coherent Intelligence boundary

The context queries only the release identities fixed at run start and contains
no score, decision, note, or zero-filled Marketplace evidence. Current
Marketplace coverage includes only complete and partial observations.
Historical scope retains every canonical release observation so unavailable
evidence is not misread as a collection removal.

The nearest earlier complete or partial same-source snapshot containing release
observations is the predecessor. Failed, empty, and source-incompatible
snapshots are skipped. With no eligible predecessor, Historical Intelligence
truthfully returns `SKIPPED`; that result remains part of the atomically
persisted complete engine execution.

Intelligence History links to canonical evidence through nullable restricted
Marketplace provenance. Exact replay is idempotent; different immutable content
for the same provenance is a conflict. Any module `FAILED` result, context
defect, serialization failure, conflict, or History write failure is fatal.
Canonical evidence already recorded remains durable. If only the later legacy
terminal write fails, both canonical and Intelligence History remain.

The desktop disables CSV import during the run, and `import_csv()` independently
guards programmatic invocation until the run terminates.

## Token boundary

The Discogs token is temporary. It is passed only to the lazy provider factory.
It is not persisted, returned in progress or results, or included in persisted
failure messages or desktop diagnostics.

## Explicitly deferred

Version 0.5.3 does not automatically import or reconcile a CSV, scope data by
Project, acquire listings,
restore sessions, enable Project Workspace refresh, cancel runs, schedule
monitoring, or change legacy scoring rules.
