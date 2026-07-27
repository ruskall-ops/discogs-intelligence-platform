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

**Status: Release candidate — v0.5.1 through v0.5.6 implemented, unreleased**

Version 0.5 establishes the collector run lifecycle and then adds limited
session restoration. Its scope assumes one collection and connects collection
refresh, existing intelligence execution, history recording, presentation
refresh, Collector Review, and primary desktop continuity through current
application boundaries.

### Version 0.5.1 — Collector Run Application Boundary

**Status: Implemented, unreleased**

The first slice extracts the existing Discogs Marketplace refresh lifecycle
from Tkinter into `CollectorRunService`. It adds immutable progress and result
models, lazy temporary-token provider construction, deterministic per-release
orchestration, one run timestamp, explicit complete/partial/failed outcomes,
and fatal-failure handling over the existing legacy `analysis_runs`,
`market_snapshots`, and score semantics.

This slice deliberately does not capture canonical aggregate Marketplace
History, execute intelligence, record Intelligence History, import a CSV, or
scope data by Project.

### Version 0.5.2 — Canonical Marketplace Capture

**Status: Implemented, unreleased**

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

### Version 0.5.3 — Coherent Intelligence Execution and History

**Status: Implemented, unreleased**

The third slice extends complete and partial canonical Collector Runs through
the existing default Collection Intelligence registry. It builds an explicit
immutable context from fixed collection evidence and canonical Marketplace
history, preserves absence, records completed and legitimate skipped results
atomically, and rejects failed-module executions.

Migration 5 adds nullable canonical Marketplace provenance to Intelligence
History with restricted referential integrity and exact replay/conflict
semantics. CSV import is disabled and guarded during a run. Package/runtime
version remains `0.4.0`; Project scoping, session restoration, scheduling,
collection-history architecture, and scoring changes remain deferred.

### Version 0.5.4 — Collector Review Workflow and Weekend Review Queue

**Status: Implemented, unreleased**

The fourth slice projects stored Hot-now scores and the latest persisted Hidden
Gems result into separate calculated observation sections. It resolves
score-origin and canonical evidence without recalculating intelligence, and
uses one observation workspace for the Dashboard count and drill-down.

Migration 6 adds the durable, user-owned Weekend Review Queue with frozen
source evidence, deterministic ordering, explicit add, notes, active/resolved
states, reopen, confirmed removal, and optimistic conflict detection. Queue
population is never automatic and Collection Decisions remain separate.
Package/runtime version remains `0.4.0`.

### Version 0.5.5 — Session Restoration

**Status: Implemented, unreleased**

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

### Version 0.5.6 — Personal-Use Release Hardening

**Status: Implemented, unreleased release candidate**

The sixth slice adds an explicit verified SQLite backup, manual recovery
documentation, fixed safe diagnostics for primary workflows, and truthful
disabled presentation for destinations without a production data path. It also
adds Linux and macOS CI, a frozen released-v0.4.0 upgrade test, fresh-install
and packaging validation, and release-candidate documentation.

It adds no schema migration: migrations remain 1–7. Package/runtime remains
0.4.0. Automatic backup, retention, in-app restore, Windows support, and a
0.5.0 release tag remain outside this implementation. A separate release step
may establish 0.5.0 only after the manual macOS and controlled real-Discogs
gates pass.

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
