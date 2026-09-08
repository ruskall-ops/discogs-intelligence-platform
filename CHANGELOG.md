# Changelog

# Version 0.6.0 — Results Presentation and UX Refinement

Released 2026-09-08. All five presentation slices are complete in v0.6.0.
v0.5.1 is the previous public release.

## Presentation and navigation

- Added shared immutable factual-state wording and detached comparison context.
- Made Price and Supply Changes summary-first, preserving exact typed values,
  classifications, missing-evidence semantics, ordering, and provenance.
- Added responsive Collection Explorer destination selection, explicit stale
  and blocked-refresh wording, keyboard shortcuts, and equivalent-content
  scroll restoration without changing refresh or cache ownership.
- Reorganised Dashboard into current collection, latest completed intelligence,
  available destinations, and unavailable destinations.
- Refined Collection Review tables, typed observation detail, disabled-action
  explanations, and keyboard/overflow behavior at `800×560`.
- Preserved exact retained Decision/Priority filter values alongside canonical
  choices. Retained filters restore as **All** under session v1; writes remain
  canonical-only.

## Terminology and compatibility

- Distinguished Previous/Latest snapshots, current catalogue metadata,
  Collector Run execution, and read-only Marketplace Changes.
- Labelled Markdown **Legacy Collector Run analysis** and Excel **Legacy
  Collector Run review analysis**, without altering filenames, worksheets,
  formulas, calculations, ordering, numeric values, or retained decisions.
- Added deterministic volume coverage for 500 Price rows, 500 Supply rows,
  75 Hidden Gems, 1,000 Collection Decisions, and 300 Observations.
- Included the post-v0.5.1 release-state documentation alignment from PR #65.

## Unchanged boundaries

- No new features beyond the accepted PRs #66–#70; no new Marketplace evidence,
  listing acquisition, recommendations, or automatic refresh.
- Migrations remain exactly 1–7; no migration 8 or schema/session change.
- Price/Supply module versions remain 2.0; Listing Price Changes and Marketplace
  Activity remain 1.0 and are not activated in production.
- Marketplace Dashboard and Project partitioning remain unavailable.
- Providers, persistence, dependencies, and analytical calculations are unchanged
  by release preparation; the canonical application version becomes `0.6.0`.

See the [v0.6.0 release notes](RELEASE_NOTES.md) for scope and limitations.

# Version 0.5.1 — Marketplace Change Explorer

Released 2 August 2026.

## Marketplace comparison and Explorer

- Added one shared canonical Marketplace comparison-window selector for Price
  Changes and Supply Changes. It selects the newest structurally eligible
  snapshot and the newest strictly earlier snapshot with exactly matching
  source and source version.
- Enabled release-level Price Changes and Supply Changes in Collection Explorer
  from that same immutable snapshot pair.
- Price Changes 2.0 compares exact same-currency observed lowest prices without
  conversion, rounding, or listing-derived reconstruction.
- Supply Changes 2.0 compares explicit observed copies-for-sale facts. Missing
  evidence remains incomparable, and availability wording is limited to
  factual zero-to-positive and positive-to-zero transitions.
- Enriched presentation with current catalogue artist/title labels while
  preserving release ID as identity and keeping those labels separate from
  historical Marketplace evidence.

## Workspace lifecycle and evidence safety

- Added lazy immutable workspace caching, explicit refresh, and preservation of
  the selected Explorer destination across successful refreshes.
- Blocked Marketplace refresh during an active Collector Run and invalidated
  stale cached comparison windows when a run completes.
- Added fixed value-neutral diagnostics and detached allowlisted provenance so
  stored payloads, provider values, paths, SQL, and exception text do not cross
  the public presentation boundary.
- Kept `listing_price_changes` 1.0 as a distinct non-production capability;
  it cannot substitute for authoritative `price_changes` 2.0.

## Important limits

- There is no listing acquisition or listing-specific production comparison.
- Rare Appearances, Marketplace Activity, Listing Lifecycle, Marketplace
  Momentum, Stability, Scarcity, and Opportunity remain unavailable in the
  production desktop path. Marketplace Activity remains non-production-wired.
- Dashboard Marketplace and Marketplace Workspace remain unavailable.
- There is no wants analysis, schema/session/persistence expansion, or schema
  migration; migrations remain exactly 1–7.
- One practical `Current Collection` remains the supported scope.

All notable changes to the Discogs Intelligence Platform will be documented here.

---

# Version 0.5.0 — Collector Workflow Foundation

Released 31 July 2026.

Version 0.5 consolidates the reviewed v0.5.1–v0.5.6 implementation slices into
the first coherent, hardened personal collector workflow.

## Collector Run, Marketplace, and Intelligence History

- Moved the synchronous per-release Discogs refresh lifecycle behind the typed
  `CollectorRunService` application boundary, with lazy provider construction,
  deterministic progress, partial and fatal outcomes, and safe diagnostics.
- Added one canonical aggregate Marketplace History snapshot for each run that
  completes all provider attempts, preserving exact `Decimal` prices, optional
  facts, provenance, and provider-neutral diagnostics.
- Integrated eligible complete and partial runs with the existing Collection
  Intelligence registry and immutable Intelligence History.
- Preserved absent evidence, recorded completed and legitimately skipped module
  results atomically, and rejected failed Intelligence executions.
- Added canonical Marketplace provenance to Intelligence History through
  migration 5 while retaining exact replay and conflict detection.

## Dashboard and Collector Review

- Integrated collection summaries, change evidence, and Hot-now attention into
  the Dashboard command centre.
- Added separate Hot now and Hidden Gems calculated observation sources without
  recalculating intelligence.
- Added the explicit, user-owned Weekend Review Queue with frozen source
  evidence, notes, active and resolved states, reopen, confirmed removal,
  optimistic concurrency, and deterministic ordering through migration 6.
- Integrated the existing Collection Decisions workflow beneath Collection
  Review while keeping decisions separate from queue state.
- Kept queue population entirely explicit; Collector Run, refresh, and
  intelligence execution never add queue items automatically.

## Session, backup, and release hardening

- Added database-scoped restoration of normal window geometry, primary and
  Collection Review navigation, filters, observation source, and exact visible
  selections through migration 7.
- Added active-Project compatibility guarding, safe restoration fallback,
  graceful close persistence, and close prevention during Collector Run.
- Added explicit, verified, atomic SQLite backup with documented manual
  recovery. Backup is user initiated; there is no schedule, retention policy,
  automatic backup, or in-app restore.
- Disabled unwired Portfolio, Marketplace, secondary Historical, and related
  Dashboard/Explorer destinations while retaining their reusable presentation
  foundations.
- Replaced raw primary-workflow failures with fixed, value-neutral diagnostics.
- Added genuine frozen-v0.4.0 upgrade validation, Linux and macOS CI,
  range-based whitespace checks, and isolated wheel/source-distribution
  installation and composition validation.

## Important limits

- Version 0.5 supports one collector and one practical `Current Collection`;
  Project identity does not partition collection, Marketplace, intelligence,
  history, queue, decision, or research data.
- There is no CSV reconciliation, Marketplace module execution, listing
  acquisition, automated backup, in-app restore, Collector Run scheduling,
  cancellation, or resumption.
- There is no cloud sync, account system, Windows support claim, or commercial
  distribution support.
- DIP remains decision support: it automates research, not buying, selling,
  pricing, or collecting decisions.

---

# Version 0.4.0 — SQLite Project Persistence

Released 24 July 2026.

- Added SQLite persistence for Project identity, active state, and deterministic
  insertion and last-opened ordering.
- Added schema migration 4 and maintained fresh-schema and migration parity.
- Added idempotent composition-root bootstrap for `Current Collection`.
- Preserved the storage-independent `ProjectRepository` boundary and
  deterministic in-memory adapter.
- Kept Project creation and opening UI, collection refresh, data partitioning,
  and session restoration outside the released scope.

---

# Sprint 2 – Collection Intelligence

## Intelligence Engine Foundation

- Added the versioned Collection Intelligence module protocol.
- Added ordered module registration with duplicate protection.
- Expanded the shared analysis context and standard result models.
- Added aggregate engine execution results and module lookup.
- Isolated module failures so later modules continue to execute.
- Added output validation and concise failure diagnostics.
- Preserved the existing application and scoring behaviour.
- Added focused registry, execution and failure-isolation tests.

## Collection Health – Issue #18

- Added the first complete Version 0.2 Collection Health vertical slice.
- Added an explainable overall health score bounded from 0 to 100.
- Added weighted metadata completeness, marketplace coverage, demand strength
  and valuation coverage components.
- Made weights, metadata fields and thresholds explicit and configurable.
- Added structured strengths, improvement opportunities, evidence and
  diagnostics to the standard intelligence result.
- Added safe handling for empty collections, missing marketplace records and
  invalid numeric evidence.
- Exposed the module for engine registration without changing desktop
  behaviour.
- Added unit coverage for strong, weak, empty and partially populated
  collections, configuration validation and engine integration.
- Confidence-adjusted demand strength by usable demand evidence coverage so
  sparse marketplace evidence cannot imply collection-wide demand strength.

## Interactive Dashboard – First Vertical Slice

- Added immutable, presentation-neutral intelligence dashboard view models.
- Added a read-only Collection Health dashboard card presenter.
- Exposed the overall health score, summary, named component scores,
  strengths, improvement opportunities, evidence and diagnostics.
- Added safe ready, skipped, failed and incomplete card states.
- Ensured dashboard presentation copies module scores without recalculating
  Collection Health.
- Preserved the existing Tkinter desktop behaviour pending a later rendering
  integration.
- Added completed, skipped, failed, incomplete, engine-integration and
  immutability tests.
- Kept Hidden Gems, Market Movers and other modules outside this slice.

## Hidden Gems Intelligence Module

- Added the complete Version 0.2 `HiddenGemsModule` vertical slice.
- Added dedicated configurable eligibility thresholds, factor weights and
  score normalisation settings.
- Added transparent demand, scarcity, community-rating, collection-ownership
  and price-efficiency factor scores.
- Added immutable ranked `HiddenGemCandidate` models containing supporting
  metrics and plain-English evidence.
- Added aggregate candidate counts, highest and average scores, ranked
  candidates, evidence and data-quality diagnostics to the standard result.
- Added safe handling for empty collections, missing marketplace data,
  missing ratings and prices, invalid values and partial evidence.
- Registered Collection Health and Hidden Gems through the explicit Version
  0.2 intelligence registry without changing desktop behaviour.
- Added deterministic-ordering, configuration, registry, failure-isolation,
  explainability and candidate-immutability tests.
- Did not add a Hidden Gems dashboard card, desktop integration, forecasting,
  machine learning or recommendation behaviour.

## Historical Intelligence – First Vertical Slice

- Added a deterministic `HistoricalIntelligenceModule` using only prepared
  `IntelligenceContext.history` evidence.
- Added immutable snapshot, release identity, release change and aggregate
  comparison models.
- Added explicit latest/preceding snapshot selection, release-ID matching,
  additions, removals and collection-size change.
- Added complete-coverage total, average and median valuation metrics with
  value changes and safe percentage handling.
- Added configurable ranked gainers and decliners with deterministic release-ID
  tie-breakers; additions and removals are excluded from movements.
- Added safe handling and diagnostics for sparse history, malformed rows,
  duplicates, empty snapshots, missing values, zero prior values, partial
  coverage and identical timestamps.
- Registered the engine-only module without desktop or dashboard changes.
- Added comprehensive module, configuration, registry, immutability and
  failure-isolation tests.

## Dashboard Integration – Version 0.2

- Integrated Collection Health, Hidden Gems and Historical Intelligence into
  the existing Tkinter dashboard.
- Added immutable presentation-specific Hidden Gems and historical card models.
- Added presenters that consume only standard `IntelligenceResult` objects and
  never calculate intelligence.
- Limited Hidden Gems to five explained releases without exposing raw scoring
  internals.
- Added snapshot dates, collection and value changes, gainers, decliners and
  evidence coverage to the historical card.
- Added unavailable and insufficient-history states with per-card failure
  isolation.
- Added application-layer context preparation using existing repository reads;
  no persistence, schema or provider changes were introduced.
- Added dashboard mapping, rendering, empty-state, isolation and context tests.

## Collection Intelligence Explorer – Version 0.2

- Added a presentation-only Explorer for Collection Health, Hidden Gems and
  Historical Intelligence.
- Reused the dashboard presentation pipeline instead of introducing a second
  `IntelligenceResult` mapping path.
- Added immutable Explorer section models and a separate desktop renderer.
- Added full explainable Hidden Gems drill-down without raw scores, factors or
  weights.
- Added historical snapshot, valuation, additions, removals, gainers,
  decliners, evidence-coverage and diagnostic drill-down.
- Added a lightweight dashboard button and three-tab, read-only Tkinter
  Explorer window.
- Preserved ready, unavailable, failed, skipped, incomplete and insufficient-
  history states independently for every section.
- Added presentation, navigation, rendering, resilience, immutability and
  desktop-controller tests.

---

# Sprint 0 – Foundation

## Documentation
- Created Vision document.
- Created Architecture document.
- Created Engineering Principles.
- Created Design Principles.
- Created Business Model.
- Created Product Positioning.
- Created Roadmap.
- Created Database design.
- Created Glossary.
- Established GitHub project structure.
- Established development workflow.

---

# Sprint 1 – Core Platform

## Database Refactor
- Refactored SQLite into a modular database package.
- Separated connection management from repository logic.
- Externalised SQL schema.
- Improved project structure.
- Updated `.gitignore` for local databases and generated files.

### Documentation

- Documented the Collection Ownership Model.
- Clarified that Discogs CSV exports do not provide unique identifiers for individual owned copies.
- Introduced the architectural distinction between Imported Facts and User Knowledge.
