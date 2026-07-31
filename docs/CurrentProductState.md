# Current Product State

## Purpose

This document distinguishes usable personal workflows from architectural
foundations. It complements the product evolution in the [Roadmap](Roadmap.md)
without treating the presence of a model, builder, or renderer as proof of a
complete desktop feature.

This is the production capability boundary for DIP v0.5.0, released on 31 July
2026 as the current public personal-use release. Application version 0.5.0 is
distinct from SQLite schema version 7 (migrations 1–7). macOS is the primary
personal-use platform; Linux receives automated headless compatibility
validation, and Windows is not supported.

## Production-wired and usable

- Project identity and the default Current Collection environment;
- Dashboard collection summaries and What Changed;
- CSV collection import and explicit Collector Run;
- Collection Health and Hidden Gems;
- Collection Explorer Overview and Collection Trends;
- Hot-now and Hidden Gems Collector Review observations;
- Weekend Review Queue;
- Collection Decisions and personal notes;
- canonical Marketplace and Intelligence History recording;
- primary desktop session restoration;
- explicit, verified database backup.

Empty queues, zero observations, and empty candidate lists remain truthful
usable states.

## Available after sufficient history

- What Changed;
- Collection Trends;
- Hidden Gems evidence and comparison-oriented summaries.

These remain enabled and explain when additional completed Collector Runs are
required.

## Visible but not available in this release

- Project Open, Create, and Project-scoped Refresh;
- Portfolio Workspace and its destinations;
- secondary Historical Intelligence workspace;
- Marketplace Workspace;
- Dashboard Portfolio, Opportunity, History, Marketplace, and Research cards;
- Collection Explorer Marketplace destinations from Weekend Listings through
  Marketplace Opportunity.

These names remain visible to communicate product direction, but their controls
are disabled and say **Not available in this release**.

## Architecture and presentation foundation only

DIP contains immutable models, intelligence modules, presentation services,
builders, and renderers for broader Marketplace, Portfolio, history, and
research experiences. They remain reusable foundations until a production
execution and data-supply path is connected.

## Deferred

Version 0.5 supports one collector and one practical `Current Collection`.
Project partitioning, CSV reconciliation, Marketplace module execution,
listing acquisition, automatic backup, in-app restore, Collector Run
scheduling, cancellation and resumption, background monitoring, accounts,
cloud sync, commercial distribution support, and automated buying or selling
remain outside the current product.
