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

The current 0.3.0 release extends intelligence beyond the collection while
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
- Project Management application service, repository contract, and in-memory
  adapter.

Version 0.3 remains a decision-support release. It does not introduce forecasts,
recommendations, alerts, automatic opportunity ranking, project persistence,
or buying and selling automation.

## Version 0.4 — Collector Workflow Foundation

**Status: Planned**

Version 0.4 will make the implemented intelligence workspaces usable as a
durable collector workflow. Candidate scope is:

- persistent Projects and session restoration behind the existing
  `ProjectRepository` boundary;
- enabled project creation and opening workflows;
- project-scoped collection refresh orchestration;
- completed Portfolio Workspace pages for Distribution, Concentration,
  Opportunity Alignment, History, and Research;
- persistent, user-owned research notes and statuses;
- watchlists, tags, and saved research views;
- clearer continuity between Project Workspace, Dashboard, Portfolio, and
  Marketplace research.

The milestone must reuse the existing Project Management, application service,
repository, presentation, and workspace boundaries. It must not turn research
state into intelligence, recommendations, or automatic decisions.

Exact 0.4 scope is not yet committed. Capabilities should enter the release only
as complete, reviewed vertical slices.

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
