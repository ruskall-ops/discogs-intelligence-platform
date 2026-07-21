# Changelog

All notable changes to the Discogs Intelligence Platform will be documented here.

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
