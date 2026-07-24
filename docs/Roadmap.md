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

**Status: Planned**

Version 0.5 will establish the collector run lifecycle before adding session
restoration. Its initial scope assumes one collection and should connect
collection refresh, existing intelligence execution, history recording, and
presentation refresh through current application boundaries.

Candidate follow-on slices include:

- session and workspace restoration after the run lifecycle is explicit;
- enabled project creation and opening only after platform data can be
  partitioned safely by Project;
- completed Portfolio Workspace destination pages;
- a user-owned **Weekend Review Queue**, distinct from the calculated
  **Weekend Marketplace Observations** intelligence;
- persistent research notes, statuses, watchlists, tags, and saved views.

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
