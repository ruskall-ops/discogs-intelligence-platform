# Discogs Intelligence Platform (DIP)

> **Transforming collections into intelligence.**

---

## Overview

The **Discogs Intelligence Platform (DIP)** is a desktop decision-support platform for serious vinyl collectors, DJs and music enthusiasts.

Its purpose is to transform a static Discogs collection into an intelligent, continuously analysed asset by combining collection data, market activity, pricing, scarcity, demand and historical trends.

DIP is **not** a replacement for Discogs.

Instead, it enhances Discogs by providing explainable insights, evidence and
historical context that help collectors make better-informed decisions.

The collector always remains in control.

---

# Mission

To build the world's best intelligence platform for vinyl collectors by **automating research rather than automating decisions.**

---

# Current Status

🚧 **Active Development**

Current release:

**Version 0.3.0 – Marketplace Intelligence and Decision Support Foundation**

Version 0.3.0 extends the released Core Platform and Collection Intelligence
foundations with Marketplace Intelligence, Portfolio Intelligence, Historical
Intelligence, explainability, and the first research-oriented Marketplace
Workspace.

---

# Completed Capabilities

Current functionality includes:

- Core platform
  - Discogs collection CSV import
  - Discogs Marketplace integration
  - SQLite persistence and ordered migrations
  - collection and Marketplace snapshots
  - configuration, reporting, search, filtering, and Excel export
- Collection Intelligence
  - deterministic, versioned Intelligence Engine
  - Collection Health
  - Hidden Gems
  - Historical Intelligence
  - Dashboard and Collection Intelligence Explorer presentation
- Marketplace Intelligence
  - Weekend Listings
  - Price Changes
  - Supply Changes
  - Rare Appearances
  - Marketplace Activity
  - Listing Lifecycle
- Marketplace Decision Intelligence
  - Marketplace Momentum
  - Marketplace Stability
  - Marketplace Scarcity
  - Marketplace Opportunity synthesis
- Portfolio Intelligence
  - Portfolio Overview
  - Portfolio Distribution
  - Portfolio Concentration
  - Portfolio Opportunity Alignment
- Historical and explainability experiences
  - immutable Intelligence History
  - Intelligence Change Analysis
  - Intelligence Trend Analysis
  - History Explorer
  - Intelligence Insights
- Marketplace Workspace
  - caller-ordered Attention Queue
  - Opportunity Detail and grouped Evidence
  - Marketplace History and Portfolio Context
  - user-owned Research Status

All intelligence remains deterministic, evidence-led, versioned, and
presentation-independent. The platform explains observed conditions and
uncertainty; it does not automate purchasing or selling decisions.

---

# Release Roadmap

## Version 0.1 – Core Platform

**Status: Released**

Established the database, import, snapshot, reporting, configuration,
migration, and modular architecture foundations.

---

## Version 0.2 – Collection Intelligence

**Status: Released**

Introduced the versioned Intelligence Engine, Collection Health, Hidden Gems,
Historical Intelligence, Dashboard, and Collection Intelligence Explorer.

---

## Version 0.3.0 – Marketplace Intelligence and Decision Support Foundation

**Status: Current**

Delivers Marketplace History and Intelligence, Marketplace Decision
Intelligence, Portfolio Intelligence, Intelligence History, Change and Trend
Analysis, History Explorer, Intelligence Insights, and Marketplace Workspace
1.0.

The release establishes decision-support and research workflows without
opportunity ranking, recommendations, predictions, alerts, or automated
decisions.

---

## Beyond Version 0.3.0

Candidate future work includes:

- richer Marketplace and Portfolio history exploration
- broader cross-module insights
- user-managed watchlists, notes, tags, and saved searches
- alerts and notifications built on explicit evidence
- dashboards, charts, and scheduled research workflows
- personalisation that remains transparent and user-controlled

These capabilities are not part of Version 0.3.0. Roadmap priorities remain
subject to architectural review and must preserve the platform’s
decision-support boundary.

---

# Product Philosophy

DIP follows one guiding principle:

> **Automate the research, not the decision.**

The platform never tells the user what they should buy or sell.

Instead, it identifies opportunities, explains the evidence and allows the collector to make the final decision.

Every surfaced assessment or insight should be:

- Transparent
- Explainable
- Evidence-based
- Reviewable over time

---

# Documentation

Detailed documentation is available in the **docs** folder.

Current documentation includes:

- [Vision](docs/vision.md)
- [Architecture](docs/Architecture.md)
- [Marketplace Architecture](docs/MarketplaceArchitecture.md)
- [Portfolio Intelligence](docs/PortfolioIntelligence.md)
- [Decision Intelligence](docs/DecisionIntelligence.md)
- [Intelligence History](docs/IntelligenceHistory.md)
- [Explorer](docs/Explorer.md)
- [Dashboard](docs/Dashboard.md)
- [Roadmap](docs/Roadmap.md)
- [Development Standard](docs/Development/DevelopmentStandard.md)
- [AI Development Playbook](docs/Development/AI_Development_Playbook.md)

---

# Technology Stack

Current technologies include:

- Python
- SQLite
- Tkinter
- Discogs API
- XlsxWriter
- Git
- GitHub
- Visual Studio Code

---

# Project Structure

DIP uses a `src`-layout Python package with capability-first boundaries:

```
discogs-intelligence-platform/
├── pyproject.toml
├── src/dip/
│   ├── app/                  # bootstrap and orchestration entry points
│   ├── config/               # typed configuration
│   ├── core/                 # provider-independent primitives
│   ├── data_sources/discogs/ # Discogs adapters
│   ├── collection/           # collection ownership and import
│   ├── marketplace/          # marketplace capability boundary
│   ├── snapshots/            # historical comparisons
│   ├── intelligence/         # engine, context, results and modules
│   ├── portfolio_intelligence/  # owned-portfolio aggregation
│   ├── decisions/            # user decisions and notes
│   ├── experience/           # desktop, dashboard, explorer, reporting
│   ├── exports/              # file export adapters
│   ├── persistence/sqlite/   # SQLite repository and migrations
│   ├── observability/        # logging and diagnostics boundary
│   └── shared/               # small cross-cutting utilities
├── tests/
└── docs/
```

The package boundaries mirror the platform architecture: external providers and presentation remain replaceable, while intelligence stays deterministic, explainable and reusable.

The Collection Intelligence foundation includes Collection Health, Hidden Gems,
and a presentation-independent Historical Intelligence comparison. Historical
Intelligence compares prepared snapshots, separates collection additions and
removals from valuation movements, and reports evidence coverage without
inventing missing values. See
[`docs/IntelligenceModules/HistoricalIntelligence.md`](docs/IntelligenceModules/HistoricalIntelligence.md).

The desktop dashboard presents these three engine results as independent,
read-only cards. Missing or failed intelligence affects only its own card, and
insufficient history is shown as an informational state. See
[`docs/Dashboard.md`](docs/Dashboard.md).

The [Collection Intelligence Explorer](docs/Explorer.md) expands those same
presentation models into read-only desktop drill-down sections. It does not
query persistence or providers and does not calculate intelligence.

[Portfolio Intelligence](docs/PortfolioIntelligence.md) provides separate
Overview, Distribution, and Concentration views over owned holdings.
Distribution describes canonical artist, label, format, release-year, and
decade membership; Concentration transparently measures mathematical clustering
within those categories. Neither adds valuation, investment-risk interpretation,
recommendations, or an overall portfolio score.

Portfolio Opportunity Alignment 1.0 is the first downstream Portfolio Decision
Intelligence synthesis. It interprets already-produced Overview, Distribution,
and Concentration results with visible evidence, rules, release/copy
denominators, reasons, and provenance. It produces no score, forecast,
valuation, recommendation, or rebalancing action.

---

# Long-Term Vision

The long-term goal is for DIP to become the first application a serious collector opens before visiting Discogs.

Rather than simply displaying a collection, DIP should answer questions such as:

- What changed this week?
- Which records deserve my attention?
- Which records are becoming scarce?
- Which records have reached all-time highs?
- Which records are becoming more desirable?
- Which opportunities am I missing?

---

# Development

DIP is being developed as a long-term software platform following modern software engineering practices including:

- Git version control
- GitHub Issues
- Milestones
- Product documentation
- Modular architecture
- Transparent scoring
- Historical data preservation

---

# Licence

Private repository.

Copyright © Russell Friend.

---

## Document Information

Version: 1.0

Status: Active

Last Updated: July 2026

Owner: Russell Friend
