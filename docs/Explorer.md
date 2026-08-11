# Collection Explorer

## Current desktop availability

Overview, Collection Health, Hidden Gems, Collection Trends, release-level Price
Changes, and release-level Supply Changes are production-wired. Price and Supply
remain selectable for data, empty, partial, insufficient-history,
insufficient-data, and safe-error states. Weekend Listings, Rare Appearances,
Marketplace Activity, Listing Lifecycle, Momentum, Stability, Scarcity, and
Opportunity remain visible but disabled as **Not available in this release**.

## Purpose

The first unified Collection Explorer is the primary desktop workspace for
detailed Collection Intelligence. It orients the user with a concise Overview,
provides the established Collection Health and Hidden Gems details, and shows a
neutral recent Collection Trends comparison and factual Weekend Listings from
an explicitly supplied Marketplace Intelligence result. Price Changes adds a
factual comparison of two explicitly supplied Marketplace snapshots.
Marketplace Momentum adds transparent, qualified Decision Intelligence from an
already-produced result.

The Explorer displays completed intelligence. It does not calculate
intelligence, make collection decisions, query persistence, or start a second
Intelligence Engine pipeline.

## Architecture

The current Dashboard homepage is the single presentation source for the
workspace:

```text
DashboardHomepageViewModel
          │
          ├── CollectionHealthPresentationService
          ├── HiddenGemsPresentationService
          ├── CollectionTrendsPresentationService
          ├── WeekendListingsPresentationService
          ├── PriceChangesPresentationService
          ├── SupplyChangesPresentationService
          ├── RareAppearancesPresentationService
          ├── MarketplaceActivityPresentationService
          ├── ListingLifecyclePresentationService
          ├── MarketplaceMomentumPresentationService
          ├── MarketplaceStabilityPresentationService
          ├── MarketplaceScarcityPresentationService
          ├── MarketplaceOpportunityPresentationService
          │
          ▼
CollectionExplorerPresentationService
          │
          ▼
CollectionExplorerViewModelBuilder
          │
          ▼
DesktopCollectionExplorerController and renderer
          │
          ▼
Collection Explorer window
```

The application service passes the exact same homepage model to the existing
detail services and builds the Explorer once when the window opens. Trends
performs one Intelligence History query during that construction. An optional,
already-produced Weekend Listings result and an optional, already-produced
Price Changes result are supplied at the same presentation boundary. Marketplace
Momentum is also supplied only as an already-produced result. Switching tabs
does not query Marketplace or Intelligence History, execute intelligence, fetch
Marketplace data, calculate a comparison or assessment, sort records, or
rebuild the workspace. On first Explorer open, a separate read-only Marketplace
Change service queries canonical Marketplace History once, selects one
exact-source/version snapshot pair, and batch-loads current artist/title labels
at most once. Its immutable workspace is cached across reopening and tab
switches. Only **Refresh Marketplace Changes** rebuilds it. Refresh preserves
the currently selected enabled destination. While Collector Run is active,
open and refresh perform no Marketplace History or metadata query and the
refresh control is disabled. The controller also enforces this boundary through
an injected read-only availability check, so direct, keyboard, programmatic,
alternate open/rebuild, Price/Supply dispatch, and renderer/controller callback
paths fail closed independently of Tk widget state. Button and keyboard
callbacks share the same guarded production boundary.
Collector Run completion invalidates the cache,
marks every live Explorer window stale with fixed copy, and enables explicit
refresh without issuing an automatic History or metadata query, provider call,
workspace rebuild, persistence write, or replacement-window creation.
An explicit refresh retains the installed cache and stale window while it builds
a candidate workspace, presentation, and fully populated replacement. Only after
all pre-publication rendering succeeds does it install the candidate and replace
the registered window. A safe workspace error or unexpected presentation
failure retains the stale content and destination, shows fixed safe failure
copy, and permits a later retry.
The replacement stages are independently regression-tested. Before publication,
failure retains the exact old cache and registered stale window; after
publication, cleanup failure retains one truthful authoritative replacement.
Hostile diagnostic and exception values are mapped to fixed safe domain,
presentation, renderer, status, stale-state, and dialog copy.

Overview, Collection Health, and Hidden Gems remain anchored to the Dashboard
homepage execution supplied when the Explorer opens. Trends identifies its
historical context explicitly with run identifiers and timestamps. Normally its
latest execution is the same completed run represented by the homepage; if the
newest historical run is not comparable (for example, every module failed),
Trends skips it and shows the older selected pair rather than implying that the
contexts match.

The older current-engine Explorer presenter remains available as a compatibility
boundary, but the desktop application no longer uses it or executes that second
pipeline.

## Destinations

Destinations use stable identifiers and always appear in this explicit order:

1. Overview;
2. Collection Health;
3. Hidden Gems;
4. Collection Trends;
5. Weekend Listings;
6. Price Changes;
7. Supply Changes;
8. Rare Appearances;
9. Marketplace Activity;
10. Listing Lifecycle;
11. Marketplace Momentum;
12. Marketplace Stability;
13. Marketplace Scarcity;
14. Marketplace Opportunity.

Overview copies existing collection size, execution status, completed-module
count, execution timestamp and version, Collection Health score, Hidden Gems
count, and recent comparison summary where those values are already available.
It does not calculate decorative statistics or interpret whether a change is
positive or negative.

Collection Health composes the existing `CollectionHealthDetailViewModel` and
uses its existing desktop renderer. Hidden Gems composes the existing
`HiddenGemsDetailViewModel` and renderer, including the complete canonical
candidate list. The Explorer does not introduce parallel detail models,
recalculate scores, filter candidates, or change candidate order.

Collection Trends uses `IntelligenceHistoryQueryService` to inspect at most the
latest five executions and selects the newest two containing a completed or
skipped module result. The displayed comparison window is exactly those two
executions. The existing Comparison Engine aligns modules; the Trends
projection exposes only neutral absolute changes for persisted collection size,
Collection Health overall and component scores, Hidden Gems count, and
completed-module count, in that canonical order. Missing values become newly
available, no longer available, or incomparable rather than fabricated.

Weekend Listings composes its immutable detail ViewModel from the typed output
of the standard `IntelligenceResult`. It preserves canonical candidate order,
exact prices and shipping, observation timestamps, optional evidence, source
diagnostics, and the explicit weekend window. The builder does not qualify,
filter, rerank, or recalculate listings. If no result is supplied, the fifth
destination remains visible with an unavailable state.

Price Changes displays only release-level observed lowest prices. It matches by
release ID, preserves exact Decimal values and signed deltas, requires matching
currencies, and treats missing facts or observations as incomparable. It emits
no listing or highest-price detail and calculates no percentage.

Supply Changes displays only explicit `num_for_sale` facts. Missing facts are
never zero; only explicit zero-to-positive and positive-to-zero transitions are
labelled became available and no copies observed for sale. Wants are excluded.

Artist and title are current collection metadata provided for identification.
They were not captured with the Marketplace snapshots. Release ID remains the
stable identity and missing metadata falls back to `Release <release_id>`.

## States and degradation

The Explorer and destinations use explicit `loading`, `available`, `partial`,
`empty`, `unavailable`, `insufficient_history`, `insufficient_data`, and `error`
states. A usable
Overview with one missing detail destination is partial rather than failed.
Empty Intelligence History produces an empty Overview and stable unavailable
detail destinations. Unexpected consistency errors continue to the desktop
error boundary. A missing Weekend Listings result is unavailable without
degrading otherwise usable collection destinations. The same applies to a
missing Price Changes result. A partial Weekend source or partial Price Changes
comparison keeps the Explorer usable and marks the aggregate workspace
partial. A missing Marketplace Momentum result is likewise unavailable without
degrading the other destinations; a partial supplied result remains usable and
makes the aggregate workspace partial. Price Changes distinguishes fewer than
two snapshots as
`insufficient_history`, two supplied but non-comparable snapshots as
`insufficient_data`, and a valid comparison with no detailed changes as
`empty`.

### Shared factual state presentation

The first Results Presentation refinement adds a small immutable shared
presentation vocabulary without replacing destination or domain states. Its
closed factual kinds cover available, no changes, empty, partial, insufficient
history, insufficient data, stale, unavailable, safe error, no imported
collection, imported but not analysed, and post-import display warning. A
deterministic allowlist supplies the exact heading, concise body, and optional
action label for each kind; callers cannot interpolate exception, diagnostic,
path, SQL, provider, snapshot, release, price, supply, or personal values into
that copy.

Price and Supply use explicit typed adapters for the states their current
results can represent truthfully. A complete comparison with one or more
established unchanged facts is **No changes observed**. A complete result with
no changed or unchanged facts remains **No matching results**. Partial,
insufficient-history, insufficient-data, and safe-error states remain distinct.
The legacy loading state has no shared factual equivalent. The legacy
unavailable detail means that no result was supplied, while the canonical
unavailable copy is reserved for a destination with no production data path;
both therefore retain their existing explicit destination copy rather than
being mapped falsely.

The same presentation boundary now exposes immutable factual summary counts
and one detached Price/Supply comparison context containing only the exact
snapshot identifiers, original aware capture times, source, and equal source
version. It performs no comparison or pair selection. The current text layout,
refresh/cache lifecycle, and evidence semantics remain unchanged.

The second Results Presentation slice projects Price and Supply into a shared
summary-first desktop hierarchy: canonical state copy, human-readable capture
period and source, factual count band, evidence limitations, typed result groups,
one section-level current-catalogue explanation, and subordinate detailed
provenance. Price groups are Increased, Decreased, Unchanged, and Incomparable;
the presentation also has closed factual observation-availability headings if
an authoritative typed result supplies them. Production Price Changes 2.0
continues to treat missing release evidence as incomparable. Supply uses the
same directional groups and reserves **Became available for sale** and **No
copies observed for sale** for explicit zero-to-positive and positive-to-zero
facts. Rows preserve exact values, currencies, signed deltas, release IDs,
metadata fallback, and canonical order without sorting or recomparison.

The tab-label and toolbar-label clipping observed during macOS smoke remains a
Slice 3 responsive-navigation acceptance requirement; this slice does not
alter notebook navigation or toolbar layout.

## Desktop navigation

The Dashboard's **Open Collection Explorer** action opens Overview in a
fourteen-tab, scrollable window. The window retains the homepage model that was
current when it opened. The action is disabled while that model is loading or
stale.

Weekend Listings is the fifth tab, Price Changes is the sixth, Supply Changes
is the seventh, Rare Appearances is the eighth, Marketplace Activity is the
ninth, Listing Lifecycle is the tenth, and Marketplace Momentum is the
eleventh, Marketplace Stability is the twelfth, and Marketplace Scarcity is
the thirteenth, and Marketplace Opportunity is the fourteenth. Opening or
selecting them performs no module execution, Marketplace
fetch, history
query, repository access, persistence write, comparison, sorting, filtering or
refresh; each only renders the result captured when the Explorer was built.

Portfolio Intelligence is intentionally outside Collection Explorer. The
separate top-level Portfolio workspace contains Overview, Distribution,
Concentration, and Opportunity Alignment.
Overview aggregates Marketplace Decision Intelligence coverage while
Distribution describes canonical collection metadata. Concentration measures
mathematical clustering within Distribution's already-produced categories.
All controllers receive already-produced results; opening Portfolio or switching tabs performs no
collection query, provider call, intelligence execution, normalization,
matching, aggregation, ratio calculation, concentration calculation, or
sorting.

Opportunity Alignment is Portfolio Decision Intelligence rather than an
Explorer feature. Its tab receives one completed result and renders its source
evidence, breadth, category composition, concentration context, rules, reasons,
provenance, and diagnostics without executing providers or joining sources.

The existing direct **Open Collection Health** and **Open Hidden Gems** actions
remain dedicated windows for compatibility and convenience. They share the
same presentation services, immutable detail models, and renderer instances as
the Explorer, so they do not maintain separate detail implementations.

## Supply Changes destination

Supply Changes is the seventh destination. It consumes an already-produced
standard result and preserves snapshot references, source, ascending release
order, supplied integer values, signed deltas, factual classifications,
summary counts, evidence, and diagnostics. It does not query history, count
listings, compare or sort. Without a supplied result it remains visible and
unavailable. Opening or switching to it performs no execution or persistence
access.

## Rare Appearances destination

Rare Appearances is the eighth destination. It receives an already-produced
result and preserves the module's frequency order, Decimal ratios, observation
boundaries, internal absence counts, snapshot identifiers, and diagnostics.
The presentation and desktop layers do not query history, count appearances,
calculate ratios, filter by threshold, or sort records.

## Marketplace Activity destination

Marketplace Activity is the ninth destination. It receives an already-produced
composite result and preserves its factual event counts, appearance facts,
observation boundaries, canonical order, and diagnostics. Explorer and desktop
code perform no source execution, aggregation, calculation, or sorting.

## Listing Lifecycle destination

Listing Lifecycle is the tenth destination. It receives an already-produced
result and preserves listing identity, lifecycle state, exact observation
facts, transition counts, canonical order, and diagnostics. Explorer and
desktop code do not query history, analyze presence, classify states,
calculate ratios, or sort records.

## Marketplace Momentum destination

Marketplace Momentum is the eleventh destination. It receives an
already-produced Decision Intelligence result and preserves source provenance,
rule-set version, price direction, supply pressure, Activity level, evidence
coverage, assessment, stable reason codes, canonical release order, and
diagnostics. Its language remains qualified and non-prescriptive: it explains
the supplied evidence without forecasting or recommending buying, selling, or
trading. Explorer and desktop code do not query snapshots or history, invoke
source providers, execute Decision Intelligence, derive components, apply
assessment rules, infer neutral or zero evidence, or sort records. Opening or
selecting the destination only renders the result captured when the Explorer
was built.

## Marketplace Stability destination

Marketplace Stability is the twelfth destination. It receives only an
already-produced Decision Intelligence result and preserves the observed
assessment, each component state, exact counts and Decimal ratios, thresholds,
evidence coverage, reason codes, provenance, rule-set version, and diagnostics.
Momentum describes observed direction while Stability describes observed
consistency; neither is a recommendation or forecast. Explorer and desktop code
do not aggregate Lifecycle facts, apply thresholds, classify stability, access
history, execute intelligence, or sort releases. A missing result remains
unavailable without degrading otherwise usable destinations.

## Marketplace Scarcity destination

Marketplace Scarcity is the thirteenth destination. It receives only an
already-produced result and preserves observed-availability, appearance, and
listing-persistence components, exact counts and Decimal ratios, thresholds,
optional factual context, evidence coverage, reason codes, provenance,
rule-set version, and diagnostics. It describes limited observed Marketplace
availability rather than absolute rarity. Explorer and desktop code perform no
Lifecycle aggregation, threshold evaluation, assessment logic, history access,
execution, or sorting. A missing result remains unavailable without degrading
the other destinations.

## Marketplace Opportunity destination

Marketplace Opportunity is the fourteenth destination. It receives only an
already-produced synthesis result and preserves Momentum, Stability, and
Scarcity assessments and evidence states separately, their mapped categories,
category counts, reason codes, provenance, diagnostics, and rule-set version.
Explorer and desktop code perform no provider calls, synthesis, source-state
mapping, rule evaluation, sorting, or lower-level intelligence access. An
absent result remains unavailable without degrading the other destinations.
The wording describes observed Marketplace alignment rather than financial
advice, value, or predicted outcomes.

## Current limitations

Search, filtering, user sorting, charts, forecasting, arbitrary date ranges,
per-release trends, Protected Records, Market Movers, automatic Marketplace
execution, live Marketplace monitoring, background refresh, and AI-generated
summaries remain outside the Collection Explorer. Marketplace results are
supplied explicitly; tab navigation never executes them.

The v0.5.5 session restores only primary desktop and Collection Review state.
It does not reopen Collection Explorer or persist its selected destination,
models, trends, ranges, or window geometry. See
[Session Restoration](SessionRestoration.md).

## Historical Intelligence desktop

Historical Intelligence is a separate top-level experience with Change
Analysis, Trend Analysis, History Explorer, and Intelligence Insights
destinations. The desktop receives already-produced models. Opening or
switching destinations performs no history retrieval, comparison, calculation,
provider execution, or sorting.
## Historical Intelligence Trend Analysis

The Historical Intelligence desktop now contains Change Analysis and Trend
Analysis destinations. Each receives an already-produced result. Opening or
switching destinations performs no retrieval, execution, joining, trend
calculation, classification, or sorting. Trend Analysis remains outside
Collection Explorer, Portfolio, and Marketplace Explorer.
## History Explorer 1.0

History Explorer is an experience, not Historical Intelligence. It browses
already-produced immutable Snapshot, Change Analysis, and Trend Analysis
ViewModels through Timeline, Snapshot, Change, Trend, and Details panes.
Presentation services remain responsible for producing those ViewModels.

The Timeline preserves supplied chronological order and exposes observation,
module, version, rule-set, snapshot and portfolio identities, assessment, and
evidence. Selection creates new immutable presentation state only. Version 1
filters only by observation number, module, module version, rule set,
portfolio identity, or snapshot identity; filtering never sorts.

The desktop Historical Intelligence workspace contains Change Analysis, Trend
Analysis, and History Explorer. Opening or selecting History Explorer performs
no history retrieval, repository query, persistence, comparison, analysis,
trend calculation, aggregation, provider execution, clock access, forecast, or
recommendation. Evolution, Metric, Reason, Diagnostic, and Alert Explorers,
automatic retrieval, charts, and arbitrary search remain deferred.
## Intelligence Insights desktop

Historical Intelligence navigation now includes Intelligence Insights beside
Change Analysis, Trend Analysis, and History Explorer. The desktop receives
already-produced insight collections and performs rendering only. Canonical
display order is overall, assessment, evidence, numeric metrics, dimensions,
reasons, diagnostics, configuration, and provenance.

Version 1 supports Snapshot, Change, and Trend insights only. AI-generated
explanations, Evolution Insights, Dashboard Insights, cross-module insights,
alerts, recommendations, predictions, scores, and confidence estimates remain
deferred.

## Marketplace Workspace desktop

Marketplace Workspace remains a reusable presentation foundation rather than a
production-operable desktop destination. Its builder and renderer can receive
an explicitly supplied, already-ordered queue of immutable presentation models
and expose Supplied Opportunities, Opportunity Detail, Evidence, Marketplace
History, Portfolio Context, and Research Status panes. The production desktop
entry point is disabled because no production data path currently supplies that
queue; invoking the disabled action does not open a controller or window.
Existing Opportunity Detail, History Explorer, and Intelligence Insights
renderers are reused; the workspace does not reproduce their calculations.

Selection and exact filtering create new immutable state and never reorder the
queue. Research status is user-owned workflow metadata, not an intelligence
assessment. Empty, unavailable, partial-history, absent-trend, and absent
portfolio-context states are rendered explicitly. Opening the experience
performs no fetching, execution, comparison, trend calculation, scoring,
ranking, persistence, recommendation, forecast, or automation.
