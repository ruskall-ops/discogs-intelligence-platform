# Discogs Intelligence Platform (DIP)

> **Transforming collections into intelligence.**

## Overview

The Discogs Intelligence Platform is a local desktop decision-support platform
for vinyl collectors, DJs, and music enthusiasts. It combines collection facts,
Marketplace observations, historical records, and deterministic intelligence
to reduce manual research and explain what deserves attention.

DIP enhances Discogs; it does not replace it. The collector remains responsible
for every buying, selling, pricing, and collection decision.

> **Automate the research, not the decision.**

## Current release

**Version 0.5.0 — Collector Workflow Foundation**

DIP v0.5.0 was released on 31 July 2026 and is the current public personal-use
release. Version 0.5 connects the single-collection Collector Run to canonical
Marketplace History, Collection Intelligence, immutable Intelligence History,
Dashboard and Collector Review workflows, the user-owned Weekend Review Queue,
Collection Decisions, primary desktop session restoration, and explicit
verified SQLite backup.

The release also makes desktop availability truthful, presents safe
value-neutral diagnostics, validates genuine v0.4.0 upgrades, and adds Linux
and macOS CI with isolated wheel and source-distribution validation.

## Implemented capabilities

### Core platform

- Discogs collection CSV import;
- Discogs Marketplace API integration;
- SQLite collection and historical storage;
- ordered, atomic schema migrations;
- configuration, collection search and filtering;
- personal decision and note fields in the collection review;
- Markdown reporting and Excel export.

### Collection Intelligence

- deterministic, versioned Intelligence Engine;
- Collection Health;
- Hidden Gems;
- Historical Intelligence over collection snapshots;
- Collection Intelligence Dashboard and Explorer presentations.

### Marketplace Intelligence

- immutable Marketplace snapshots and deterministic serialization;
- Marketplace History repository and SQLite adapter;
- Weekend Listings;
- Price Changes;
- Supply Changes;
- Rare Appearances;
- Listing Lifecycle;
- Marketplace Activity.

### Decision Intelligence

- Marketplace Momentum;
- Marketplace Stability;
- Marketplace Scarcity;
- Marketplace Opportunity synthesis.

These modules expose separate components, evidence, diagnostics, provenance,
and rule-set versions. They do not forecast or recommend actions.

### Portfolio Intelligence

- Portfolio Overview;
- Portfolio Distribution;
- Portfolio Concentration;
- Portfolio Opportunity Alignment.

Portfolio outputs preserve owned-release and owned-copy denominators and do not
introduce valuation, investment-risk, or rebalancing advice.

### History and explainability

- immutable Intelligence History;
- deterministic comparison;
- Intelligence Change Analysis;
- Intelligence Trend Analysis;
- History Explorer;
- Intelligence Insights.

Historical analysis consumes previously calculated intelligence. It does not
recalculate the original modules or predict a future state.

### Desktop workspaces

- **Project Workspace** is the application entry point. It presents one
  persisted active Project, recent-project state, a summary, and navigation to
  Dashboard and Portfolio Workspace.
- **Dashboard** is the command centre. Eight summary cards answer what changed,
  what deserves attention, and where to investigate next.
- **Collection Explorer** provides production-wired Overview, Collection
  Health, Hidden Gems, and Collection Trends.
- Portfolio, secondary Historical Intelligence, Marketplace Workspace, and
  Marketplace-oriented Explorer destinations retain architectural foundations
  but are visibly disabled as **Not available in this release** until a real
  production data path supplies them.

Workspace builders compose immutable presentation models. They do not execute
intelligence, query persistence, or duplicate application and presentation
services.

### Project Management

The Project Management application layer provides:

- immutable `ManagedProject` application models;
- a storage-independent `ProjectRepository` protocol;
- deterministic `InMemoryProjectRepository`;
- SQLite-backed `SQLiteProjectRepository`;
- list, create, open, active, last-opened, and recent-project workflows through
  `ProjectManagementService`.

Normal desktop execution persists Project identity, deterministic insertion and
last-opened order, and active-project state in the existing SQLite database.
The composition root creates `Current Collection` once on a new database and
reuses it thereafter. Project creation UI, file selection, collection refresh,
and secondary-workspace restoration remain planned work. The Version 0.5
primary desktop session restores normal geometry, primary navigation,
filters, and stable visible selections, using active Project identity only as a
compatibility guard.

Project identity does not yet partition collection, Marketplace, intelligence,
history, or research data. Version 0.5 therefore remains a practical
single-collection workflow; multi-project UI is deferred until those data
boundaries are genuinely Project-scoped.

## Architecture

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

Intelligence and domain services remain independent of presentation and
persistence. Application Services prepare inputs and coordinate repositories
or engines. The composition root constructs concrete SQLite and in-memory
adapters and injects them into the desktop application.

The main architectural rules are:

- identical inputs and versions produce identical outputs;
- intelligence is immutable, versioned, explainable, and
  presentation-independent;
- historical records are append-only through their repository boundaries;
- Presentation Services map completed results without recalculation;
- Workspaces compose presentation models and navigation only;
- repositories reconstruct domain models and contain no business logic;
- external provider details do not leak into intelligence or UI code.

See [Architecture](docs/Architecture.md) for the complete implemented
architecture.

## Package structure

```text
src/dip/
├── app/                              application and presentation services
├── collection/                       collection import
├── collector_review/                 observations and review queue
├── comparison/                       historical comparison
├── config/                           typed settings
├── core/                             shared errors and primitives
├── data_sources/discogs/             Discogs adapter
├── decision_intelligence/            Marketplace Decision Intelligence
├── experience/                       view models, builders, workspaces, desktop
├── exports/                          Excel export
├── historical_intelligence/          change and trend analysis
├── intelligence/                     engine, context, registry, modules
├── intelligence_history/             history models and serialization
├── marketplace_history/              Marketplace repository contract
├── marketplace_intelligence/         Marketplace intelligence modules
├── persistence/sqlite/               database, schema, migrations, adapters
├── portfolio_decision_intelligence/  Opportunity Alignment
├── portfolio_intelligence/           portfolio modules
├── projects/                          Project models and repository contract
├── session/                           primary desktop session models
├── database_backup.py                 backup domain models
└── composition.py                    desktop dependency composition
```

## Roadmap summary

- **0.1 — Core Platform:** released.
- **0.2 — Collection Intelligence:** released.
- **0.3 — Marketplace Intelligence and Decision Support:** released.
- **0.4 — SQLite Project Persistence:** released.
- **0.5 — Collector Workflow Foundation:** released on 31 July 2026; current
  package/runtime version is 0.5.0.

See the [Roadmap](docs/Roadmap.md) for release scope and future direction.

## Documentation

- [Vision](docs/Vision.md)
- [Session Restoration](docs/SessionRestoration.md)
- [Backup and Recovery](docs/BackupAndRecovery.md)
- [Current Product State](docs/CurrentProductState.md)
- [Release Checklist](docs/ReleaseChecklist.md)
- [Architecture](docs/Architecture.md)
- [Roadmap](docs/Roadmap.md)
- [Configuration](docs/Configuration.md)
- [Project Workspace](docs/ProjectWorkspace.md)
- [Marketplace Architecture](docs/MarketplaceArchitecture.md)
- [Portfolio Intelligence](docs/PortfolioIntelligence.md)
- [Decision Intelligence](docs/DecisionIntelligence.md)
- [Intelligence History](docs/IntelligenceHistory.md)
- [Dashboard](docs/Dashboard.md)
- [Collection Explorer](docs/Explorer.md)
- [Development Standard](docs/Development/DevelopmentStandard.md)
- [AI Development Playbook](docs/Development/AI_Development_Playbook.md)
- [Project Bootstrap](PROJECT_BOOTSTRAP.md)

Additional module and future-design documents live under `docs/`. A document
describing a proposed module is not evidence that the module is implemented;
the release list above and the source tree are authoritative for current
capability.

## Technology

- Python;
- Tkinter;
- SQLite;
- Discogs API;
- XlsxWriter;
- pytest;
- Git and GitHub.

## Install and launch

DIP requires Python 3.11 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
dip
```

`python -m dip` and the root `python app.py` compatibility launcher are also
supported. The SQLite database uses `DIP_DATABASE_FILENAME` when supplied and
otherwise defaults to `discogs_intelligence.db` in the launch directory.

macOS is the primary personal-use platform after manual release smoke testing.
Linux receives automated headless compatibility validation. Windows is not
supported or verified.

Use **Back Up Database…** for an explicit complete SQLite backup. DIP does not
schedule, retain, upload, or restore backups automatically; see
[Backup and Recovery](docs/BackupAndRecovery.md).

## Development

The repository follows an architecture-first, vertical-slice workflow. Read the
[Development Standard](docs/Development/DevelopmentStandard.md) and
[AI Development Playbook](docs/Development/AI_Development_Playbook.md) before
changing implementation. New work must preserve deterministic behaviour,
immutable boundaries, explicit ordering, focused tests, and the separation
between intelligence, application, persistence, presentation, and workspace
responsibilities.

## Long-term direction

DIP aims to become the first application a serious collector opens before
visiting Discogs by answering:

- What changed?
- What deserves my attention?
- What evidence supports that assessment?
- Where should I investigate next?

Long-term possibilities include broader history, additional replaceable data
providers, evidence-based alerts, and privacy-preserving platform intelligence.
They must remain transparent, user-controlled, and consistent with the product
principle.

## Licence

Private repository.

Copyright © Russell Friend.
