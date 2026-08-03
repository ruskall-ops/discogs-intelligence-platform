# Discogs Intelligence Platform Roadmap

## Purpose

This roadmap describes product evolution rather than a backlog of historical
implementation tasks. Release status follows the software currently present on
`main`. Future scope is directional and remains subject to architectural
review.

Every release follows the same product principle:

> **Automate the research, not the decision.**

## Version 0.1 — Core Platform

**Status: Released**

Version 0.1 established the local desktop and data foundations:

- Discogs collection CSV import;
- Discogs Marketplace API integration;
- SQLite collection and snapshot storage;
- ordered schema migrations;
- configuration and error boundaries;
- collection search, filtering, review, and personal decision fields;
- Markdown reporting and Excel export;
- automated tests and the `src`-layout package structure.

## Version 0.2 — Collection Intelligence

**Status: Released**

Version 0.2 transformed the collection tool into a deterministic intelligence
platform:

- versioned Intelligence Engine and registry;
- Collection Health;
- Hidden Gems;
- Historical Intelligence over collection snapshots;
- immutable Dashboard presentation;
- Collection Health and Hidden Gems detail experiences;
- Collection Intelligence Explorer;
- architecture-first development standards.

## Version 0.3 — Marketplace Intelligence and Decision Support

**Status: Released**

Version 0.3 extended intelligence beyond the collection while
preserving evidence and user control:

- immutable Marketplace models, serialization, history repository, and SQLite
  persistence;
- Weekend Listings, Price Changes, Supply Changes, Rare Appearances, Listing
  Lifecycle, and Marketplace Activity;
- Marketplace Momentum, Stability, Scarcity, and Opportunity synthesis;
- Portfolio Overview, Distribution, Concentration, and Opportunity Alignment;
- Intelligence History, comparison, Change Analysis, Trend Analysis, History
  Explorer, and Intelligence Insights;
- Marketplace Workspace and the first Portfolio Workspace vertical slice;
- Dashboard command centre with deterministic workspace navigation;
- Project Workspace as the desktop entry point;
- Project Management application service and repository contract.

Version 0.3 remained a decision-support release. It did not introduce
forecasts, recommendations, alerts, automatic opportunity ranking, Project
persistence, or buying and selling automation.

## Version 0.4 — SQLite Project Persistence

**Status: Released**

Version 0.4 established the durable Project persistence boundary:

- SQLite implementation of the existing `ProjectRepository` contract;
- persistent Project identity and active-project state;
- deterministic insertion and last-opened ordering;
- schema migration 4 with fresh-schema and migration parity;
- idempotent creation and reuse of the default `Current Collection` Project.

This release persists Project metadata only. It does not partition collection,
Marketplace, intelligence, history, or research data by Project, restore a
desktop session, enable project create/open UI, or run a Project-scoped
collection refresh. The practical released workflow therefore remains one
collection.

## Version 0.5 — Collector Run Pipeline

**Status: Released as Version 0.5.0 on 31 July 2026**

Version 0.5 establishes the collector run lifecycle and then adds limited
session restoration. Its scope assumes one collection and connects collection
refresh, existing intelligence execution, history recording, presentation
refresh, Collector Review, and primary desktop continuity through current
application boundaries.

### Version 0.5 development slice 1 — Collector Run Application Boundary

**Status: Released in Version 0.5.0**

The first slice extracts the existing Discogs Marketplace refresh lifecycle
from Tkinter into `CollectorRunService`. It adds immutable progress and result
models, lazy temporary-token provider construction, deterministic per-release
orchestration, one run timestamp, explicit complete/partial/failed outcomes,
and fatal-failure handling over the existing legacy `analysis_runs`,
`market_snapshots`, and score semantics.

This slice deliberately does not capture canonical aggregate Marketplace
History, execute intelligence, record Intelligence History, import a CSV, or
scope data by Project.

### Version 0.5 development slice 2 — Canonical Marketplace Capture

**Status: Released in Version 0.5.0**

The second slice records one immutable canonical Marketplace aggregate for
each Collector Run that finishes every provider attempt. It preserves exact
optional provider facts, maps complete, partial and failed evidence with safe
diagnostics, reuses the existing Marketplace History command and SQLite
repository, and retains the legacy snapshot and scoring workflow through an
explicit compatibility projection.

Canonical capture uses deterministic `collector-run-{analysis_run_id}`
identity. It occurs before the
legacy terminal write, so immutable canonical evidence remains valid if that
later write fails. This slice added no schema, Project scope, Intelligence
execution, Intelligence History, CSV reconciliation, scheduling, cancellation,
or package-version change.

### Version 0.5 development slice 3 — Coherent Intelligence Execution and History

**Status: Released in Version 0.5.0**

The third slice extends complete and partial canonical Collector Runs through
the existing default Collection Intelligence registry. It builds an explicit
immutable context from fixed collection evidence and canonical Marketplace
history, preserves absence, records completed and legitimate skipped results
atomically, and rejects failed-module executions.

Migration 5 adds nullable canonical Marketplace provenance to Intelligence
History with restricted referential integrity and exact replay/conflict
semantics. CSV import is disabled and guarded during a run. Project scoping,
scheduling, collection-history architecture, and scoring changes remain
deferred.

### Version 0.5 development slice 4 — Collector Review Workflow and Weekend Review Queue

**Status: Released in Version 0.5.0**

The fourth slice projects stored Hot-now scores and the latest persisted Hidden
Gems result into separate calculated observation sections. It resolves
score-origin and canonical evidence without recalculating intelligence, and
uses one observation workspace for the Dashboard count and drill-down.

Migration 6 adds the durable, user-owned Weekend Review Queue with frozen
source evidence, deterministic ordering, explicit add, notes, active/resolved
states, reopen, confirmed removal, and optimistic conflict detection. Queue
population is never automatic and Collection Decisions remain separate.

### Version 0.5 development slice 5 — Session Restoration

**Status: Released in Version 0.5.0**

The fifth slice restores a deliberately small database-scoped desktop session:
normal main-window geometry, primary and Collection Review navigation, stable
filters and observation source, and exact visible observation, queue, and
decision selections. Migration 7 adds an empty singleton session table behind
a storage-independent repository and application service.

Restoration queries fresh state before applying selections, uses the active
Project only as a compatibility guard, and falls back without mutation.
Graceful close preserves the Review-note draft lifecycle, offers an explicit
choice when session saving fails, and refuses close during Collector Run.

Search text, drafts, calculated models, secrets, secondary windows, non-normal
window states, Project partitioning, and resumable Collector Runs remain
excluded. See [Session Restoration](SessionRestoration.md).

### Version 0.5 development slice 6 — Personal-Use Release Hardening

**Status: Released in Version 0.5.0**

The sixth slice adds an explicit verified SQLite backup, manual recovery
documentation, fixed safe diagnostics for primary workflows, and truthful
disabled presentation for destinations without a production data path. It also
adds Linux and macOS CI, a frozen released-v0.4.0 upgrade test, fresh-install
and packaging validation, and release documentation.

It adds no schema migration: migrations remain 1–7. Automatic backup,
retention, in-app restore, and Windows support remain outside Version 0.5.

These six internal development slices were consolidated into the public v0.5.0
release; their numbering does not represent later public releases.

## Version 0.5.1 — Marketplace Change Explorer

**Status: Released on 2 August 2026**

DIP v0.5.1 was released on 2 August 2026 and is the latest completed, tagged
public personal-use release. Its annotated tag and GitHub release exist.

Version 0.5.1 enables release-level observed lowest-price and copies-for-sale
changes in Collection Explorer. Both views share one exact-source/version
snapshot pair, use current catalogue labels only for identification, and remain
read-only. Listing-dependent and composite Marketplace features remain disabled.
The released target also includes truthful transactional CSV-import feedback.

## Results Presentation and UX Refinement

**Status: Future milestone; no public version assigned**

This milestone makes existing factual results easier to understand, navigate,
compare, and act upon without changing their evidence semantics. Presentation
must consume existing immutable typed results; it cannot reinterpret missing
evidence or change domain calculations. It aligns with the established
[Collection Explorer](Explorer.md), [Dashboard](Dashboard.md),
[Marketplace Architecture](MarketplaceArchitecture.md), [Architecture](Architecture.md),
and [Current Product State](CurrentProductState.md) boundaries.

The presentation scope is:

- a clearer summary-first hierarchy with compact overview counts before detail;
- concise plain-language explanations for available, partial, empty,
  insufficient-history, insufficient-data, stale, and safe-error states;
- clearer separation of comparison context, totals, factual details, current
  metadata labels, provenance, evidence limitations, and warnings;
- clearer Price and Supply change grouping, with consistent positive, negative,
  unchanged, incomparable, and availability-transition presentation;
- more readable tables through deliberate spacing, headings, alignment, and
  scanning, plus user-friendly filtering and sorting over already calculated
  results;
- stable selection and navigation, clearer refresh and stale-state affordances,
  and useful empty states with next-step guidance;
- accessibility improvements for keyboard navigation, focus order, selectable
  text, contrast, and screen-reader-friendly labels where Tk supports them;
- consistent terminology across Dashboard, Explorer, exports, and documentation;
- exact preservation of Decimal values, currencies, release IDs, snapshot
  provenance, current-metadata labelling, and evidence limitations;
- macOS visual smoke coverage using realistic result volumes.

The milestone explicitly excludes new Marketplace evidence, listing acquisition
or history, Rare Appearances or Marketplace Activity activation, scoring,
recommendations, demand, liquidity, scarcity, opportunity, or advisory
conclusions. It also excludes presentation-driven schema changes, persisted
presentation caches, provider calls during tab switching, automatic refresh or
Collector Run, Project partitioning, Dashboard Marketplace activation without
separate approval, and web, cloud, account, or commercial-distribution work.

Candidate follow-on slices include:

- enabled project creation and opening only after platform data can be
  partitioned safely by Project;
- completed Portfolio Workspace destination pages;
- broader persistent research workflows such as watchlists and saved views,
  only after their ownership and Project-scoping boundaries are designed.

Multi-project UI is deliberately deferred until collection, Marketplace,
intelligence, history, and research data are genuinely Project-scoped. Research
workflow state must remain separate from calculated intelligence and must not
become a recommendation or automatic decision.

## Future vision

Beyond the Collector Workflow Foundation, DIP may evolve toward:

- richer multi-period history and visual exploration;
- broader collection, Marketplace, and portfolio evidence;
- evidence-based alerts and scheduled research;
- additional replaceable market-data providers;
- transparent personalisation controlled by the collector;
- privacy-preserving, anonymous platform intelligence when product maturity and
  adoption justify it;
- alternative read-only interfaces over the same application boundaries.

The following remain outside the roadmap unless separately designed and
approved:

- automated buying, selling, listing, or pricing;
- opaque investment scores or return forecasts;
- high-frequency market automation;
- exposing individual collection data to other users.

Long-term ideas belong in vision or future-module documents. Concrete delivery
work belongs in reviewed milestones and issues, not in a duplicate sprint
ledger inside this roadmap.
