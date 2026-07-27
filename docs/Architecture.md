# Discogs Intelligence Platform — Architecture

## Purpose

This document describes the architecture implemented by the Discogs
Intelligence Platform (DIP). It records the current implemented component
boundaries, dependency direction, data flows, and constraints that future work
must preserve.

DIP is a single-user Python desktop decision-support platform. It imports a
Discogs collection, preserves collection and Marketplace observations,
calculates deterministic intelligence, and presents evidence-led research
workflows. Its governing principle is:

> **Automate the research, not the decision.**

The platform does not automate buying, selling, pricing, or collecting
decisions.

## Implemented architecture

The implementation uses a `src`-layout package, a Tkinter desktop shell, SQLite
adapters, immutable models, application services, and explicit dependency
composition.

```text
Desktop UI
    ↓
Workspaces
    ↓
Presentation Services
    ↓
Application Services
    ↓
Repository Interfaces
    ↓
Persistence
    ↓
External Providers
```

This diagram describes responsibility and dependency boundaries, not a rule
that every use case must traverse every layer. Intelligence modules sit beside
application orchestration: application services prepare typed inputs and
execute them, while presentation receives only completed results or immutable
presentation models.

```text
External observations / collection facts
                    ↓
          Application Services
                    ↓
      Intelligence and domain services
                    ↓
        immutable IntelligenceResult
                    ↓
         Presentation Services
                    ↓
       Workspaces and Desktop UI
```

The composition root in `dip.composition` is the only place that assembles the
concrete desktop dependency graph. It constructs SQLite repositories,
application services, intelligence modules, presentation services, workspace
builders, and desktop controllers. Renderers do not instantiate repositories
or engines.

## Architectural responsibilities

### Desktop UI

`dip.experience.desktop` contains the Tkinter application and renderers. The
desktop:

- displays immutable presentation models;
- handles user input and deterministic navigation;
- starts application workflows through injected controllers and services;
- renders loading, empty, partial, unavailable, and error states.

It must not contain SQL, intelligence rules, comparisons, persistence
transactions, or provider-specific business logic.

The Project Workspace is the application entry point. The Dashboard remains the
command centre after project entry, while Collection Explorer, Portfolio
Workspace, Marketplace Workspace, and Historical Intelligence provide focused
research destinations.

### Workspaces

Workspace packages under `dip.experience` are orchestration and navigation
boundaries over immutable presentation models:

- Project Workspace;
- Dashboard command centre;
- Collection Explorer;
- Collection Review;
- Portfolio Workspace;
- Marketplace Workspace;
- History Explorer.

Workspace builders are deterministic. They compose supplied models, preserve
canonical order, and replace immutable navigation state. They do not execute
intelligence, retrieve history, access repositories, or reproduce presentation
mapping.

### Presentation Services

Application-facing presentation services in `dip.app` coordinate builders
under `dip.experience`. Presentation models are frozen and independent of
Tkinter.

Presentation may select, validate, label, and format already-produced facts.
It must not recalculate scores, interpret history, query persistence, contact a
provider, or create domain conclusions.

### Application Services

Application services coordinate complete use cases. Implemented examples
include:

- the Collector Run legacy Discogs refresh stage;
- collection import and Dashboard homepage assembly;
- Intelligence History execution and read-only queries;
- Marketplace History commands and queries;
- Marketplace, Decision, Portfolio, and Historical Intelligence execution;
- Project Management;
- workspace presentation composition.

Application services depend on repository protocols and explicit collaborators.
They may select inputs, validate compatibility, and coordinate an engine or
repository. They do not instantiate concrete SQLite adapters.

### Collector Run application boundary

`CollectorRunService` owns the existing per-release Discogs Marketplace
refresh lifecycle over the collection already stored in SQLite. The desktop
supplies a temporary token and progress callback, then renders progress and the
terminal result. The service owns lazy provider construction, deterministic
release iteration, one UTC capture timestamp, legacy `analysis_runs`,
`market_snapshots`, current legacy score updates, canonical aggregate
Marketplace capture, and request throttling.
Eligible canonical evidence then passes to the injected Collection Intelligence
execution service, which builds an explicit context, runs the default registry,
and records Intelligence History.

Only provider-call failures are recoverable per release. Fatal persistence,
scoring, callback, or internal failures cause the service to attempt to fail
the parent analysis run and raise an application error with the original cause.
Observations written before a fatal network-spanning run may remain, but their
failed parent is excluded from completed-run queries.

After every provider attempt and successful legacy write/score lifecycle has
finished, a pure mapper constructs one immutable aggregate
`MarketplaceSnapshot`. `CollectorRunService` records it through the injected
Marketplace History command boundary before writing the legacy terminal state.
Exact and optional provider facts remain canonical; a separate legacy
projection owns existing defaults and float conversion. Canonical failure is a
fatal application failure. Canonical evidence may remain if the later legacy
terminal write fails.

CSV import remains a separate optional collection-update action. Collector Run
disables and guards that mutation while active. Complete and partial canonical
captures produce one provenance-linked Intelligence History execution.
Completed and legitimately skipped results are persisted atomically in registry
order; any failed module or downstream context/history failure makes the run
fatal without discarding canonical evidence already recorded. See [Collector
Run](CollectorRun.md).

### Intelligence and domain services

Intelligence modules are deterministic, presentation-independent calculators.
They consume typed contexts or typed outputs from earlier intelligence layers
and return standard, versioned `IntelligenceResult` values.

Implemented intelligence layers are:

```text
Collection Intelligence
        ├── Collection Health
        ├── Hidden Gems
        └── Historical Intelligence

Marketplace Primary Intelligence
        ├── Weekend Listings
        ├── Price Changes
        ├── Supply Changes
        ├── Rare Appearances
        └── Listing Lifecycle
                    ↓
Marketplace Composite Intelligence
        └── Marketplace Activity
                    ↓
Marketplace Decision Intelligence
        ├── Marketplace Momentum
        ├── Marketplace Stability
        ├── Marketplace Scarcity
        └── Marketplace Opportunity

Portfolio Intelligence
        ├── Portfolio Overview
        ├── Portfolio Distribution
        └── Portfolio Concentration
                    ↓
Portfolio Decision Intelligence
        └── Portfolio Opportunity Alignment

Historical Intelligence
        ├── Intelligence Change Analysis
        └── Intelligence Trend Analysis
```

Primary intelligence owns factual calculation. Composite intelligence combines
already-produced facts. Decision Intelligence applies visible, versioned rules
without forecasting or recommending actions. Presentation never substitutes
for any of these layers.

### Repository interfaces

Repository contracts are storage-independent, narrow, and expressed in domain
terms. Implemented contracts cover collection storage, Intelligence History,
Marketplace History, and Project Management.

Repositories:

- preserve deterministic ordering;
- return reconstructed domain models, not raw database rows;
- use `None` for singular absence and immutable empty collections for plural
  absence where the local contract specifies;
- reject malformed stored data;
- contain no intelligence or presentation logic.

### Persistence

`dip.persistence.sqlite` implements SQLite connection management, schema
creation, migrations, collection data access, Intelligence History, Marketplace
History, and Project persistence.

SQLite is the persistent source of truth for implemented collection and history
data. Historical observations are append-only through their repository
contracts. Writes use explicit transaction boundaries, deterministic
serialization, and savepoint isolation when nested in an existing transaction.
Fresh schema creation and ordered migrations are kept equivalent.

Normal desktop composition uses `SQLiteProjectRepository`.
`InMemoryProjectRepository` remains a deterministic alternative and test
adapter. Project content, insertion and last-opened order, and the active
Project identity persist across database reopen. Session and workspace state do
not.

### External providers

`dip.data_sources.discogs` contains the Discogs API adapter, while
`dip.collection.importers` contains the Discogs CSV importer. Provider-specific
payloads are normalised before they reach intelligence. External access is
replaceable and does not occur from domain, presentation, workspace, or
renderer code. The composition root supplies the provider type to
`CollectorRunService`; it does not construct a provider or make a network
request at startup.

## Project Management architecture

A Project is the root of the user experience, not a file or persistence model.
The implemented flow is:

```text
Desktop Project Workspace
            ↓
ProjectWorkspacePresentationService
            ↓
ProjectManagementService
            ↓
ProjectRepository
            ↓
SQLiteProjectRepository
            ↓
shared SQLite Database boundary
```

`ProjectManagementService` supports listing, creating, opening, selecting the
active project, updating last-opened state, and returning recent projects.
`ManagedProject` is an immutable application model. The presentation service
maps it into separate immutable Project Workspace models.

The composition root idempotently creates one active `Current Collection`
Project on a new database. Later starts reuse existing Projects and active
state without duplicating or overwriting that default. Opening a Project
atomically advances its application-controlled last-opened order and changes
the active identity through the repository.

Open Project, Create Project, and Refresh Collection remain disabled UI
placeholders; only navigation to Dashboard and Portfolio Workspace is wired.
Filesystem selection, collection refresh, and session or workspace restoration
remain future work.

Project persistence currently stores Project metadata only. Collection,
Marketplace, intelligence, history, and research records are not partitioned
by Project identity. The released desktop therefore supports a practical
single-collection workflow; multi-project UI must wait for genuine
Project-scoped data boundaries.

## Current desktop workflows

### Dashboard

The Dashboard command centre composes existing Dashboard, Portfolio,
Marketplace, and Historical presentation state into eight deterministic cards:
Portfolio Summary, Portfolio Health, Opportunity Highlights, Collection
Changes, Historical Changes, Marketplace Highlights, Research Summary, and
Quick Actions. Its actions open existing workspace controllers.

The earlier Collection Intelligence Dashboard homepage and its dedicated
Collection Health and Hidden Gems detail views remain active presentation
components. Dashboard refresh also obtains one immutable Collector Review
observation workspace: its Hot-now count and drill-down therefore describe the
same calculated rows.

### Portfolio Workspace

Portfolio Workspace provides left navigation for Overview, Distribution,
Concentration, Opportunity Alignment, History, and Research. In the implemented
first slice, only Overview is complete; it composes all four existing Portfolio
presentation models. The other five destinations render explicit placeholders.
Navigation state is immutable, but the navigation model still marks those
destinations as unimplemented.

### Marketplace Workspace

Marketplace Workspace composes caller-supplied Opportunities, Opportunity
Detail, Evidence, Marketplace History, Portfolio Context, and Research Status.
Opportunity order comes from the caller and never implies ranking or a
recommendation. Research status is user-owned workflow metadata and is not
persisted by this slice.

### Collection and Historical experiences

Collection Explorer presents Collection Health, Hidden Gems, Collection Trends,
and the implemented Marketplace Intelligence and Marketplace Decision
Intelligence destinations. Historical Intelligence presents Change Analysis,
Trend Analysis, History Explorer, and Intelligence Insights from
already-produced models.

Collection Review contains three deliberately separate destinations:
calculated **Observations**, the user-owned **Weekend Review Queue**, and
**Collection Decisions**. Observation projection reads stored Hot-now scores,
Intelligence History, and canonical Marketplace evidence without executing
intelligence. Only an explicit user Add creates a durable queue item. Frozen
source evidence does not change when later Collector Runs refresh calculated
observations, and Collection Decisions continue to use their independent
editor and persistence. See [Collector Review](CollectorReview.md).

## Data and history boundaries

DIP preserves three distinct kinds of history:

- Collection History records collection and legacy market observations;
- Marketplace History stores immutable aggregate Marketplace snapshots;
- Intelligence History stores immutable, versioned module results.

The histories are not interchangeable. Intelligence History does not replace
raw observations, and Marketplace History does not store conclusions.
Comparison and Trend Analysis consume completed historical intelligence; they
do not recalculate the source intelligence.

Complex persisted values pass through explicit deterministic serializers and
type allow-lists. Unknown tags, unsupported types, malformed payloads,
non-finite decimals, and inconsistent stored metadata are rejected.

## Dependency and ordering rules

Dependencies point from UI and orchestration toward abstractions and domain
logic. Domain code must not import Tkinter, SQLite adapters, migrations, or
provider clients.

Identical inputs and versions must produce identical outputs. All ordered
queries and presentation sequences define stable ordering, including
secondary identifiers where timestamps may tie. Builders preserve supplied
canonical order unless their contract explicitly owns ordering.

## Failure behaviour

Failures are explicit and local where possible:

- one intelligence module may fail without invalidating unrelated results;
- missing evidence is represented as unavailable, partial, limited, skipped,
  or insufficient rather than invented;
- repositories reject corruption rather than silently repairing it;
- transaction failure leaves no partial history execution;
- presentation preserves diagnostics and does not hide domain failures.

## Security and privacy

API tokens, personal databases, imported collection files, private exports, and
logs containing personal information must not be committed. DIP is currently a
local single-user desktop application. Multi-user hosting, authentication,
payments, and community-data aggregation are outside the implemented
architecture.

## Deliberate non-goals

The current architecture does not implement:

- automated purchasing, selling, listing, bidding, or pricing;
- forecasts or investment-return predictions;
- opaque overall decision scores;
- session or workspace restoration;
- complete Portfolio Workspace destination pages;
- saved research notes, watchlists, or alerts;
- background scheduling or live monitoring;
- multi-user cloud operation;
- cross-provider Marketplace aggregation.

Future work must extend existing service and repository boundaries rather than
placing these concerns in workspaces or renderers.

## Package map

```text
src/dip/
├── app/                              application and presentation services
├── collection/                       collection import workflows
├── comparison/                       historical comparison domain
├── config/                           typed configuration
├── core/                             shared errors and primitives
├── data_sources/discogs/             Discogs provider adapter
├── decision_intelligence/            Marketplace Decision Intelligence
├── experience/                       immutable UI models, builders, renderers
├── exports/                          Excel export
├── historical_intelligence/          change and trend analysis
├── intelligence/                     engine, contexts, modules, registry
├── intelligence_history/             history models, contracts, serialization
├── marketplace_history/              Marketplace History repository contract
├── marketplace_intelligence/         Marketplace intelligence modules
├── persistence/sqlite/               SQLite adapters, schema, migrations
├── portfolio_decision_intelligence/  Portfolio Opportunity Alignment
├── portfolio_intelligence/           portfolio aggregation modules
├── projects/                          Project models and repository boundary
└── composition.py                    concrete desktop dependency assembly
```

Some compatibility packages remain intentionally small or reserved
(`marketplace`, `decisions`, `observability`, `shared`, and
`intelligence.persistence`). Their presence does not imply an implemented
capability.

## Architectural rule

> **Collect once, preserve history, analyse transparently, explain clearly, and
> leave the decision to the collector.**
