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

**Version 0.3.0 — Marketplace Intelligence and Decision Support**

Versions 0.1, 0.2, and 0.3 are released. The current release includes the
Marketplace, Portfolio, Historical, Workspace, Dashboard, and Project
Management foundations described below. Version 0.4, the Collector Workflow
Foundation, is planned.

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
  in-memory active project, recent-project state, a summary, and navigation to
  Dashboard and Portfolio Workspace.
- **Dashboard** is the command centre. Eight summary cards answer what changed,
  what deserves attention, and where to investigate next.
- **Portfolio Workspace** provides an implemented Overview that composes
  Portfolio Overview, Distribution, Concentration, and Opportunity Alignment.
  Distribution, Concentration, Opportunity Alignment, History, and Research
  remain visible placeholder destinations in the workspace navigation.
- **Marketplace Workspace** provides Attention Queue, Opportunity Detail,
  Evidence, Marketplace History, Portfolio Context, and Research Status.
- **Collection Explorer** and the Historical Intelligence desktop provide
  detailed collection, Marketplace, change, trend, history, and insight views.

Workspace builders compose immutable presentation models. They do not execute
intelligence, query persistence, or duplicate application and presentation
services.

### Project Management

The Project Management application layer provides:

- immutable `ManagedProject` application models;
- a storage-independent `ProjectRepository` protocol;
- deterministic `InMemoryProjectRepository`;
- list, create, open, active, last-opened, and recent-project workflows through
  `ProjectManagementService`.

Version 0.3.0 does not persist Projects. The composition root seeds one
`Current Collection` project for the process. Project creation UI, file
selection, durable storage, and session restoration remain planned work.

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
└── composition.py                    desktop dependency composition
```

## Roadmap summary

- **0.1 — Core Platform:** released.
- **0.2 — Collection Intelligence:** released.
- **0.3 — Marketplace Intelligence and Decision Support:** released; current
  package version is 0.3.0.
- **0.4 — Collector Workflow Foundation:** planned, including completion of the
  Portfolio Workspace, durable Projects, and user-owned research workflow.

See the [Roadmap](docs/Roadmap.md) for release scope and future direction.

## Documentation

- [Vision](docs/Vision.md)
- [Architecture](docs/Architecture.md)
- [Roadmap](docs/Roadmap.md)
- [Project Workspace](docs/ProjectWorkspace.md)
- [Marketplace Architecture](docs/MarketplaceArchitecture.md)
- [Portfolio Intelligence](docs/PortfolioIntelligence.md)
- [Decision Intelligence](docs/DecisionIntelligence.md)
- [Intelligence History](docs/IntelligenceHistory.md)
- [Dashboard](docs/Dashboard.md)
- [Collection Explorer](docs/Explorer.md)
- [Development Standard](docs/Development/DevelopmentStandard.md)
- [AI Development Playbook](docs/Development/AI_Development_Playbook.md)

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
