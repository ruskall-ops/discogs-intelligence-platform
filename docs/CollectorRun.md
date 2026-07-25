# Collector Run

## Purpose

Collector Run is the application boundary for recurring collector workflows
over the collection already stored in SQLite. Version 0.5.1 implements only
the existing Discogs Marketplace refresh stage.

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
existing score function, application version, configured delay, UTC clock, and
wait function. Provider construction remains lazy and occurs only for a
non-empty stored collection when `run()` is called.

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
10. completes or fails the parent legacy analysis run and returns an immutable
    terminal result.

The capture timestamp is reused for every observation and score in the run.
Release order, failed release identities, and progress order are deterministic.
Malformed, duplicate, boolean, or non-positive release identities are rejected
before the analysis run starts.

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

## Token boundary

The Discogs token is temporary. It is passed only to the lazy provider factory.
It is not persisted, returned in progress or results, or included in persisted
failure messages or desktop diagnostics.

## Explicitly deferred

Version 0.5.1 does not create canonical aggregate `MarketplaceSnapshot`
records, write Marketplace History, execute any Intelligence module, record
Intelligence History, import a CSV, scope data by Project, restore sessions,
enable Project Workspace refresh, cancel runs, schedule monitoring, or change
legacy scoring rules. Later Collector Run slices must extend this application
boundary without moving orchestration back into the desktop.
