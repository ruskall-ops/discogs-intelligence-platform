# Discogs Intelligence Platform — Architecture

## Document Purpose

This document defines the technical architecture of the Discogs Intelligence Platform (DIP).

It explains:

- how the platform is divided into components;
- where responsibilities belong;
- how data moves through the system;
- how the platform should evolve;
- which architectural boundaries future development must preserve.

This is a living document. It should be updated whenever a significant architectural decision changes.

---

## Architectural Vision

DIP is designed as a modular, database-backed decision-support platform for vinyl collectors.

The architecture must support the core principle:

> **Automate the research, not the decision.**

The platform collects data, preserves history, calculates transparent metrics, identifies noteworthy changes and presents evidence to the user.

It must not automatically decide what the user should buy, keep, list or sell.

---

## Current State

The current application is a working desktop prototype built with:

- Python
- Tkinter
- SQLite
- Discogs API
- CSV collection imports
- XlsxWriter
- Git and GitHub

The current source files are:

```text
app.py
database.py
discogs_client.py
scoring.py
report.py
requirements.txt
```

The current application already supports:

- importing a Discogs collection CSV;
- storing releases in SQLite;
- retrieving live Discogs marketplace data;
- preserving market snapshots;
- calculating initial scores;
- saving personal decisions and notes;
- searching and filtering the collection;
- exporting results to Excel.

The current implementation proves the product concept. It is not yet the final project structure.

---

## Target Architecture

The target architecture separates the system into independent layers:

```text
┌───────────────────────────────────────────────────────┐
│                    User Interface                     │
│         Dashboard · Search · Review · Settings        │
└──────────────────────────┬────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────┐
│                  Application Services                 │
│   Collection Review · Refresh Runs · User Decisions   │
└──────────────────────────┬────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────┐
│                  Intelligence Layer                   │
│ Analysis · Scoring · Opportunities · Explanations     │
└──────────────────────────┬────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────┐
│                     Data Layer                        │
│ Repositories · SQLite · History · Configuration       │
└──────────────────────────┬────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────┐
│                   Integration Layer                   │
│       Discogs API · CSV Import · Future Sources       │
└───────────────────────────────────────────────────────┘
```

Each layer has a clear responsibility and should not take over the responsibilities of another layer.

---

# Architectural Principles

## 1. Separation of Concerns

Each module should have one clear responsibility.

Examples:

- the Discogs client retrieves external data;
- the database layer stores and retrieves data;
- the scoring engine calculates scores;
- the opportunity engine classifies noteworthy records;
- the user interface displays results and accepts input;
- the reporting layer creates exports.

The user interface must not contain scoring or database logic.

The database layer must not make product decisions.

---

## 2. SQLite as the Source of Truth

The SQLite database is the permanent source of truth for:

- collection records;
- marketplace snapshots;
- calculated scores;
- analysis runs;
- user decisions;
- protected records;
- personal notes;
- application settings.

Excel workbooks and CSV files are imports or exports. They are not the primary datastore.

---

## 3. Historical Data Is Immutable

Historical market snapshots must never be overwritten.

Each refresh creates a new snapshot associated with:

- a release;
- an analysis run;
- a timestamp;
- the source of the data.

Corrections should be recorded explicitly rather than silently replacing historical observations.

This allows DIP to calculate reliable changes over time.

---

## 4. Transparent Intelligence

Every calculated score must be reproducible from stored data and documented rules.

Every highlighted record should include an explanation of:

- why it was selected;
- which data points influenced its classification;
- what changed;
- how confident the platform is in the available evidence.

Black-box recommendations are outside the intended architecture.

---

## 5. User Decisions Remain Separate from Market Signals

Market intelligence and personal preference are different concepts.

For example:

- a record may have a strong market opportunity score;
- the user may still mark it as `Never Sell`.

The platform must store both facts without allowing one to overwrite the other.

Personal decisions should influence presentation and filtering, not corrupt the underlying market analysis.

---

## 6. External Services Must Be Replaceable

Discogs is the first major data provider, but it should not be permanently embedded throughout the application.

External integrations should sit behind defined interfaces so future sources can be added, such as:

- eBay sold listings;
- Popsike;
- Juno Records;
- Bandcamp;
- Resident Advisor;
- Beatport;
- YouTube;
- Mixcloud;
- Google Trends.

The core intelligence engine should operate on normalised internal data rather than provider-specific response formats.

---

## 7. Build Incrementally

The architecture describes the intended destination, not a requirement to build everything immediately.

New structure should be introduced when it improves:

- maintainability;
- clarity;
- reliability;
- testing;
- development speed.

The project should avoid premature complexity.

---

# Logical Components

## Core

The Core component contains shared platform functions that do not belong to a specific feature.

Responsibilities may include:

- application configuration;
- logging;
- error definitions;
- date and time utilities;
- common types;
- validation utilities;
- application metadata and versioning.

Core must not depend on the desktop interface.

---

## Configuration

The Configuration component manages user-adjustable and system-level settings.

Examples:

- database path;
- default currency;
- refresh interval;
- scoring weights;
- minimum value threshold;
- shortlist size;
- reporting options;
- data-provider settings.

Secrets such as API tokens must not be committed to Git.

Personal access tokens should remain temporary unless secure credential storage is deliberately implemented.

---

## Integration Layer

The Integration layer communicates with external systems.

### Discogs API Client

Responsibilities:

- authenticate API requests;
- retrieve release information;
- retrieve marketplace statistics;
- respect rate limits;
- handle retries and transient errors;
- convert Discogs responses into internal data objects;
- report failures without crashing an entire refresh.

It must not calculate scores or directly update the interface.

### CSV Importer

Responsibilities:

- read official Discogs collection exports;
- identify required columns;
- validate release IDs;
- normalise field names;
- report malformed rows;
- return structured import data.

It must not contain database-specific SQL.

### Future Providers

Each future provider should implement a common contract where practical.

For example:

```python
class MarketDataProvider:
    def fetch_release_data(self, release_id: int) -> MarketObservation:
        ...
```

This enables the intelligence layer to consume data consistently.

---

## Data Layer

The Data layer provides all persistent storage operations.

### Database Connection

Responsibilities:

- open and close database connections;
- apply SQLite settings;
- manage transactions;
- initialise the schema;
- run migrations.

### Repositories

Database access should gradually be separated into repository classes.

Potential repositories:

```text
ReleaseRepository
CollectionRepository
MarketSnapshotRepository
ScoreRepository
DecisionRepository
AnalysisRunRepository
SettingsRepository
```

A repository owns the queries for one area of the data model.

Other layers should not contain raw SQL once the repository structure is established.

### Database Migrations

Schema changes must be versioned.

Future versions should not rely only on `CREATE TABLE IF NOT EXISTS`.

A migration system should record:

- schema version;
- migration identifier;
- date applied;
- migration status.

This protects existing user databases as DIP evolves.

---

## Import Engine

The Import Engine coordinates collection imports.

Typical flow:

```text
User selects CSV
        ↓
CSV Importer reads and validates rows
        ↓
Import Engine normalises records
        ↓
Release Repository inserts or updates releases
        ↓
Import result is recorded
        ↓
UI displays summary and errors
```

The import process must be repeatable.

Importing a newer collection export should update existing records without creating duplicate releases.

---

## Refresh Engine

The Refresh Engine coordinates marketplace data collection.

Typical flow:

```text
Refresh requested
        ↓
Analysis run created
        ↓
Release IDs loaded
        ↓
External data requested
        ↓
Responses normalised
        ↓
Snapshots saved
        ↓
Scores recalculated
        ↓
Opportunities classified
        ↓
Run completed with summary
```

The Refresh Engine is responsible for orchestration, not for implementing API, database or scoring details itself.

A refresh should record:

- start time;
- completion time;
- releases attempted;
- successful requests;
- failed requests;
- data provider;
- application version;
- final status.

Interrupted refreshes should eventually support resumption.

---

# Intelligence Layer

## Analysis Engine

The Analysis Engine converts stored market observations into meaningful metrics.

Potential analyses include:

- demand level;
- demand growth;
- supply level;
- supply tightening;
- scarcity;
- price change;
- market activity;
- volatility;
- collection concentration;
- data confidence.

The Analysis Engine should produce factual metrics before any weighted scoring occurs.

---

## Scoring Engine

The Scoring Engine converts normalised metrics into separate, explainable scores.

Planned scores include:

- Value Score;
- Demand Score;
- Scarcity Score;
- Liquidity Score;
- Momentum Score;
- Confidence Score;
- Opportunity Score.

Independent scores must remain visible.

The Opportunity Score is a configurable weighted combination rather than a replacement for the underlying scores.

Detailed scoring definitions belong in `docs/Scoring.md`.

---

## Opportunity Engine

The Opportunity Engine classifies records into useful review categories.

Potential classifications include:

- Weekend Listing Candidate;
- Hidden Gem;
- Hot Now;
- Rising;
- Valuable but Slow;
- Scarce and Hard to Replace;
- Cooling;
- Bundle Candidate;
- Protected Keeper.

The Opportunity Engine does not issue commands.

It produces:

- a classification;
- supporting evidence;
- a plain-English explanation;
- a confidence level;
- a review priority.

---

## “Why Now?” Engine

The “Why Now?” Engine explains why a record has become noteworthy during the current analysis.

It may compare:

- current Wants against previous Wants;
- current supply against historical supply;
- current price against historical prices;
- current score against previous scores;
- current classification against previous classifications.

Example output:

```text
Why now?

- Wants increased by 18% since the previous snapshot.
- Available supply fell from 11 copies to 4.
- The lowest listing increased by 22%.
- The record entered the High-priority review category.
```

Explanations must be derived from stored evidence.

---

## Personal Intelligence

Personal Intelligence stores and applies user preferences without replacing objective analysis.

Examples:

- Keep;
- Never Sell;
- List for Sale;
- Maybe;
- Ignore;
- Would Miss It;
- Protected;
- personal notes.

Future personalisation may identify patterns in user decisions, but recommendations must remain transparent.

The platform must never imply that inferred preferences are facts.

---

# Application Services

Application Services coordinate complete user workflows.

Potential services include:

```text
ImportCollectionService
RefreshMarketDataService
ReviewCollectionService
SaveDecisionService
GenerateWeekendListingsService
ExportReportService
BackupDatabaseService
```

These services call lower-level components in the correct sequence.

They provide a clean boundary between the user interface and the underlying architecture.

---

# User Interface

## Current Interface

The current interface uses Tkinter and provides:

- a dashboard;
- CSV import;
- Discogs data refresh;
- a searchable collection table;
- filters;
- record review;
- personal decisions;
- notes;
- Excel export.

Tkinter is appropriate for the current desktop prototype.

---

## UI Responsibilities

The interface may:

- display data;
- accept user input;
- trigger application services;
- show progress;
- show validation errors;
- open record detail views.

The interface must not:

- execute raw SQL;
- calculate scores;
- call Discogs directly;
- contain core business rules;
- silently modify historical data.

---

## Future Interface Options

Potential future interfaces include:

- an improved Tkinter desktop interface;
- a local web application;
- a cross-platform desktop application;
- a read-only mobile companion.

Changing the interface should not require rewriting the data and intelligence layers.

This separation is an important architectural objective.

---

# Reporting Layer

The Reporting layer creates outputs from database queries and application services.

Initial outputs include:

- Excel collection review;
- opportunity shortlists;
- historical change reports;
- dashboard summaries.

Future outputs may include:

- PDF reports;
- weekly intelligence reports;
- insurance reports;
- CSV exports;
- charts;
- email summaries.

Reports must read from the database and must not become an alternative source of truth.

---

# Logging and Error Handling

DIP should maintain structured logs for:

- application start and shutdown;
- imports;
- refresh runs;
- API failures;
- rate-limit events;
- database errors;
- report generation;
- unexpected exceptions.

Errors should be categorised where practical:

```text
ValidationError
ImportError
ProviderError
RateLimitError
DatabaseError
ScoringError
ReportError
ConfigurationError
```

The application should fail gracefully.

One failed release request should not normally terminate an entire collection refresh.

---

# Testing Strategy

Testing should be added as the architecture is modularised.

## Unit Tests

Unit tests should cover isolated logic such as:

- scoring formulas;
- data normalisation;
- opportunity classification;
- change calculations;
- validation.

## Integration Tests

Integration tests should cover:

- database repositories;
- CSV import;
- schema migrations;
- refresh orchestration;
- report generation.

## Fixtures

Tests should use small, controlled datasets rather than the user's live collection database.

No real API token should be required for routine automated tests.

External API responses should be mocked.

---

# Security and Privacy

DIP handles personal collection information and API credentials.

The following rules apply:

- API tokens must not be committed to Git;
- personal databases must not be committed to Git;
- collection CSV exports must not be committed to Git;
- generated private reports must not be committed by default;
- logs must not expose credentials;
- backups must be clearly identifiable as personal data.

The `.gitignore` file should exclude at least:

```text
__pycache__/
*.pyc
*.db
*.sqlite
*.sqlite3
*.csv
*.xlsx
.env
.DS_Store
```

If DIP later supports multiple users, authentication and data separation will require a dedicated security design.

---

# Proposed Project Structure

The project should gradually move toward the following structure:

```text
discogs-intelligence-platform/
│
├── README.md
├── requirements.txt
├── pyproject.toml
├── .gitignore
│
├── docs/
│   ├── Vision.md
│   ├── Architecture.md
│   ├── DevelopmentPrinciples.md
│   ├── Database.md
│   ├── Scoring.md
│   ├── Roadmap.md
│   └── ProductPositioning.md
│
├── src/
│   └── dip/
│       ├── __init__.py
│       ├── application/
│       │   ├── import_service.py
│       │   ├── refresh_service.py
│       │   ├── review_service.py
│       │   └── export_service.py
│       │
│       ├── core/
│       │   ├── config.py
│       │   ├── errors.py
│       │   ├── logging.py
│       │   └── types.py
│       │
│       ├── integrations/
│       │   ├── discogs_client.py
│       │   └── csv_importer.py
│       │
│       ├── database/
│       │   ├── connection.py
│       │   ├── migrations/
│       │   └── repositories/
│       │
│       ├── intelligence/
│       │   ├── analysis.py
│       │   ├── scoring.py
│       │   ├── opportunities.py
│       │   ├── explanations.py
│       │   └── personalisation.py
│       │
│       ├── reporting/
│       │   ├── excel.py
│       │   └── weekly_report.py
│       │
│       └── ui/
│           ├── app.py
│           ├── dashboard.py
│           ├── collection_review.py
│           └── record_detail.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── scripts/
    └── run_dip.py
```

This structure is a target, not an instruction to move every file immediately.

Refactoring should occur in controlled, testable stages under the Core Platform milestone.

---

# Primary Data Flow

The main data flow is:

```text
Discogs CSV / External API
            ↓
     Integration Layer
            ↓
  Validation and Normalisation
            ↓
     Application Services
            ↓
      Repository Layer
            ↓
      SQLite Database
            ↓
       Analysis Engine
            ↓
       Scoring Engine
            ↓
     Opportunity Engine
            ↓
 User Interface and Reports
            ↓
       User Decisions
            ↓
      SQLite Database
```

External source data and user decisions both enter the database, but remain logically distinct.

---

# Dependency Direction

Dependencies should generally point inward:

```text
UI
 ↓
Application Services
 ↓
Intelligence and Domain Logic
 ↓
Repositories
 ↓
Database / External Integrations
```

Core analysis must not depend on Tkinter.

Database code must not depend on Excel.

Discogs-specific response structures must not leak into every module.

---

# Background Processing

Long-running tasks such as full Discogs refreshes must not freeze the interface.

The current threading approach is acceptable for the prototype.

Future implementation should provide:

- cancellable refreshes;
- reliable progress events;
- clear completion status;
- retry tracking;
- resumable runs;
- safe database writes from background tasks.

The UI should receive progress updates through a controlled interface rather than modifying widgets from arbitrary worker code.

---

# Backup and Recovery

The SQLite database contains the user's intelligence history and personal decisions.

The architecture must eventually support:

- manual backup;
- automatic timestamped backup;
- restore;
- integrity checks;
- safe schema migration;
- retention settings.

Before any database migration, DIP should create or request a backup.

---

# Performance and Scale

The initial target is a personal collection of approximately 1,000–10,000 releases.

The architecture should remain practical for larger collections, but it does not need enterprise-scale infrastructure.

Performance priorities include:

- indexed snapshot queries;
- paginated or virtualised UI tables;
- avoiding unnecessary API calls;
- incremental refreshes where possible;
- batch database transactions;
- cached derived results;
- efficient historical comparisons.

SQLite is appropriate for the foreseeable single-user desktop use case.

---

# Future Extensibility

The architecture should allow future modules without requiring a rewrite.

Potential modules include:

- completed-sales valuation;
- DJ and chart signals;
- market-wide watchlists;
- buying intelligence;
- portfolio analytics;
- collection insurance;
- mobile read-only access;
- AI-generated summaries.

New features should build on the same stored evidence and service boundaries.

---

# Deliberate Non-Goals

The architecture is not currently designed for:

- automated Discogs listing;
- automated buying or selling;
- high-frequency marketplace activity;
- multi-user cloud hosting;
- payment processing;
- marketplace order fulfilment;
- replacing Discogs' catalogue or marketplace.

These may require fundamentally different security, legal and operational designs.

---

# Architectural Decision Process

Major technical decisions should be documented before or alongside implementation.

Each significant decision should record:

- the problem;
- available options;
- the chosen approach;
- reasons for the choice;
- consequences and trade-offs.

A future `docs/decisions/` directory may hold Architecture Decision Records.

Example:

```text
docs/decisions/
├── 0001-use-sqlite.md
├── 0002-retain-tkinter-for-prototype.md
└── 0003-store-immutable-market-snapshots.md
```

---

# Definition of Architectural Success

The architecture is successful when:

- modules have clear responsibilities;
- external data sources can be changed or added;
- calculations can be tested without opening the UI;
- the interface can change without replacing the database;
- reports can change without changing core analysis;
- historical information remains reliable;
- personal decisions persist;
- scores remain transparent;
- new features can be added without destabilising unrelated components.

---

# Guiding Architectural Rule

> **Collect once, preserve history, analyse transparently, explain clearly and leave the decision to the collector.**