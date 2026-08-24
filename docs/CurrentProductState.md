# Current Product State

## Purpose

This document distinguishes usable personal workflows from architectural
foundations. It complements the product evolution in the [Roadmap](Roadmap.md)
without treating the presence of a model, builder, or renderer as proof of a
complete desktop feature.

This is the released DIP v0.5.1 capability boundary. DIP v0.5.1 was released on
2 August 2026 and is the latest completed, tagged public personal-use release.
Its annotated tag and GitHub release exist. The released target includes the
truthful transactional CSV-import feedback correction. Application version
0.5.1 is distinct from SQLite schema
version 7 (migrations 1–7). macOS is the primary personal-use platform; Linux
receives automated headless compatibility validation, and Windows is not
supported.

## Production-wired and usable

- Project identity and the default Current Collection environment;
- Dashboard collection summaries and What Changed;
- CSV collection import and explicit Collector Run;
- Collection Health and Hidden Gems;
- Collection Explorer Overview and Collection Trends;
- Collection Explorer release-level Price Changes and Supply Changes;
- Hot-now and Hidden Gems Collector Review observations;
- Weekend Review Queue;
- Collection Decisions and personal notes;
- canonical Marketplace and Intelligence History recording;
- primary desktop session restoration;
- explicit, verified database backup.

Empty queues, zero observations, and empty candidate lists remain truthful
usable states.

The current authoritative Price Changes and Supply Changes modules use version
2.0 semantics. Historical persisted 1.0 results retain their original module
identity and are not silently reinterpreted.

Unreleased work on the unversioned Results Presentation milestone now includes
shared immutable factual-state copy and comparison context, a summary-first
Price/Supply layout, responsive Collection Explorer navigation, and Dashboard
and Collection Review readability refinements. The six
production-enabled destinations use a full-label selector backed by one
authoritative availability registry; unavailable destinations remain visible
and explicitly explained outside it. Canonical stale and Collector-Run-blocked
refresh copy, displayed keyboard shortcuts, equivalent-content scroll
restoration, and the complete main-toolbar **Marketplace** label are included.
The released Price/Supply evidence, classification, ordering, transactional
replacement, query/cache, provider, persistence, and session lifecycles remain
unchanged. Dashboard now separates collection facts from latest completed
intelligence and separates active from unavailable destinations. Collection
Decisions retains all columns with numeric alignment and horizontal overflow;
selected observations use typed detail sections and actions expose disabled
reasons. Collection Decision and Priority filters expose canonical choices plus
exact retained stored values; retained choices are session-local and safely
persist as **All**, while decision writes remain canonical-only. Latest
intelligence contains only execution-bound History values;
mutable legacy score aggregates remain available through their existing
workflows without being attributed to that execution. Queue, evidence,
provider, and persistence lifecycles remain unchanged. These changes are
unreleased and are not part of v0.5.1.

The final terminology audit adds an unreleased presentation-only glossary.
Marketplace comparisons say **Previous snapshot** and **Latest snapshot**;
present-day artist/title identification is **Current catalogue metadata** or
**current collection labels** and is never represented as captured snapshot
evidence. **Collector Run** remains the explicit provider-backed workflow,
while **Marketplace Changes** remains the read-only Price/Supply comparison.
Legacy Markdown and Excel outputs are now labelled **Legacy Collector Run
analysis** without changing any stored or exported calculation value. This
work remains outside the released v0.5.1 capability boundary.

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
- Collection Explorer Weekend Listings, Rare Appearances, Marketplace Activity,
  Listing Lifecycle, Momentum, Stability, Scarcity, and Opportunity.

These names remain visible to communicate product direction, but their controls
are disabled and say **Not available in this release**.

## Architecture and presentation foundation only

DIP contains immutable models, intelligence modules, presentation services,
builders, and renderers for broader Marketplace, Portfolio, history, and
research experiences. They remain reusable foundations until a production
execution and data-supply path is connected.

## Deferred

Version 0.5 supports one collector and one practical `Current Collection`.
Project partitioning, CSV reconciliation, listing acquisition, composite or
listing-dependent Marketplace execution, automatic backup, in-app restore, Collector Run
scheduling, cancellation and resumption, background monitoring, accounts,
cloud sync, commercial distribution support, and automated buying or selling
remain outside the current product.
