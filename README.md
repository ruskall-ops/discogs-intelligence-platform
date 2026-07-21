# Discogs Intelligence Platform (DIP)

> **Transforming collections into intelligence.**

---

## Overview

The **Discogs Intelligence Platform (DIP)** is a desktop decision-support platform for serious vinyl collectors, DJs and music enthusiasts.

Its purpose is to transform a static Discogs collection into an intelligent, continuously analysed asset by combining collection data, market activity, pricing, scarcity, demand and historical trends.

DIP is **not** a replacement for Discogs.

Instead, it enhances Discogs by providing insights, historical context and transparent recommendations that help collectors make better-informed decisions.

The collector always remains in control.

---

# Mission

To build the world's best intelligence platform for vinyl collectors by **automating research rather than automating decisions.**

---

# Current Status

🚧 **Active Development**

Current Milestone:

**Version 0.1 – Core Platform**

---

# Current Features

Current functionality includes:

- Import Discogs Collection CSV
- Discogs Marketplace Integration
- SQLite Database
- Historical Market Snapshots
- Opportunity Scoring
- Personal Decisions & Notes
- Search & Filtering
- Excel Export

These features will continue to evolve as the platform develops.

---

# Planned Roadmap

## Version 0.1 – Core Platform

- SQLite Database
- Import Engine
- Historical Snapshots
- Reporting Engine
- Configuration System
- Modular Architecture

---

## Version 0.2 – Collection Intelligence

- Collection Intelligence Engine foundation
- Versioned module registry
- Standard analysis context and results
- Failure-isolated module execution
- Collection Health module (Issue #18)
  - 0–100 explainable health score
  - weighted component scores
  - strengths, improvement opportunities, evidence and diagnostics
- Hidden Gems intelligence module
  - immutable ranked research candidates
  - demand, scarcity, community-rating, ownership and price-efficiency factors
  - configurable thresholds, weights, evidence and diagnostics
- Interactive Dashboard foundation
  - presentation-neutral intelligence view models
  - read-only Collection Health card
  - safe ready, skipped, failed and incomplete states
- Weekend Listings
- Dashboard
- Opportunity Engine
- Protected Records
- Collection Health

---

## Version 0.3 – Market Intelligence

- Price History
- Demand Momentum
- Scarcity Trends
- Weekly Intelligence Reports
- Why Now? Engine
- Market Trend Detection

---

## Version 0.4 – Personal Intelligence

- Collector DNA
- Decision Tracking
- Recommendation Memory
- Personal Recommendation Engine

---

# Product Philosophy

DIP follows one guiding principle:

> **Automate the research, not the decision.**

The platform never tells the user what they should buy or sell.

Instead, it identifies opportunities, explains the evidence and allows the collector to make the final decision.

Every recommendation should be:

- Transparent
- Explainable
- Evidence-based
- Reviewable over time

---

# Documentation

Detailed documentation is available in the **docs** folder.

Current documentation includes:

- Vision.md
- Architecture.md
- Dashboard.md
- IntelligenceModules/CollectionIntelligence.md
- IntelligenceModules/HiddenGems.md
- DevelopmentPrinciples.md *(in progress)*
- Roadmap.md *(planned)*
- ProductPositioning.md *(planned)*
- Database.md *(planned)*
- Scoring.md *(planned)*
- Development/DevelopmentStandard.md – engineering and implementation standards
- Development/AIDevelopmentPlaybook.md – AI-assisted development workflow

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

Version 0.2 intelligence currently includes Collection Health, Hidden Gems and
a presentation-independent Historical Intelligence comparison. Historical
Intelligence compares the latest two prepared snapshots, separates collection
additions and removals from valuation movements, and reports evidence coverage
without inventing missing values. See
[`docs/IntelligenceModules/HistoricalIntelligence.md`](docs/IntelligenceModules/HistoricalIntelligence.md).

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
