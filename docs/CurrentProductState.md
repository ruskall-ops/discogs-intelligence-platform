# Current Product State

## Purpose

This document distinguishes usable personal workflows from architectural
foundations. It complements the product evolution in the [Roadmap](Roadmap.md)
without treating the presence of a model, builder, or renderer as proof of a
complete desktop feature.

This document records the current released baseline. DIP v0.6.0 is the current
public personal-use release, dated 2026-09-08. DIP v0.5.1 is the previous public
release. The v0.6.0 target includes the
truthful transactional CSV-import feedback correction. Application version
0.6.0 is distinct from SQLite schema
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

All five Results Presentation slices are complete and released in v0.6.0. Their
scope includes
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
provider, and persistence lifecycles remain unchanged.

The final terminology audit adds a presentation-only glossary.
Marketplace comparisons say **Previous snapshot** and **Latest snapshot**;
present-day artist/title identification is **Current catalogue metadata** or
**current collection labels** and is never represented as captured snapshot
evidence. **Collector Run** remains the explicit provider-backed workflow,
while **Marketplace Changes** remains the read-only Price/Supply comparison.
Legacy Markdown output is labelled **Legacy Collector Run analysis** and Excel
output **Legacy Collector Run review analysis**, without changing any stored
or exported calculation value. This
work extends the previous v0.5.1 capability boundary.

The [v0.6.0 release notes](../RELEASE_NOTES.md) and
[release checklist](ReleaseChecklist.md) record the released scope and
publication procedure.

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

The Current Collection Portfolio application foundation can now execute the
existing Distribution module once and pass that exact typed result to
Concentration once. It validates module/rule-set versions, typed outputs, and
status/state consistency before publishing a separate immutable pair. Concrete
version-1 validators in each owning domain reconstruct the typed outputs, and
an execution envelope plus source-consistency check prevents independently
calculated results from being paired. The bounded application snapshots retain
only module metadata, explanatory text, the typed output, evidence, and
diagnostics—not the source metrics dictionaries. Execution cleanup covers every exit while system-level
`BaseException` signals continue to propagate.
Overlap and same-thread re-entry are rejected without starting module work;
the last complete pair is retained only in memory for that coordinator's
lifetime. It remains lazy and read-only, identifies only the one database-wide
Current Collection, and does not make Projects owners of collection data. This is not yet a
production desktop workflow: Portfolio toolbar, Dashboard, and Project entry
points remain unavailable until later presentation and UI slices.

The desktop-neutral Current Collection Portfolio presentation foundation now
projects that complete pair into exactly two fixed destinations: Distribution
and Concentration. It exposes collection totals, full-denominator metadata
coverage, represented-membership concentration measures, provenance, and
truthful missing/unavailable states. Domain Decimal values and ordering remain
unchanged; secondary percentages use two-decimal `ROUND_HALF_EVEN` display
rounding. The presentation has no Tk, query, write, provider, history, or
calculation boundary. Its fixed terminology and formatted text are derived
from closed identifiers and factual values, and its immutable models reject
contradictory structural combinations without restricting dynamic evidence.
Portfolio is still unavailable in the production
desktop: toolbar, Dashboard, and Project controls are unchanged, and the
window, refresh, stale/import lifecycle, focus, and scrolling work remain for
the later desktop slice.

## Deferred

Version 0.5 supports one collector and one practical `Current Collection`.
Project partitioning, CSV reconciliation, listing acquisition, composite or
listing-dependent Marketplace execution, automatic backup, in-app restore, Collector Run
scheduling, cancellation and resumption, background monitoring, accounts,
cloud sync, commercial distribution support, and automated buying or selling
remain outside the current product.
