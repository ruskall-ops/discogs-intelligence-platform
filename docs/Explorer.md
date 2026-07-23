# Collection Explorer

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
rebuild the workspace.

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
12. Marketplace Stability.

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

Price Changes likewise consumes the typed output of an already-produced
standard `IntelligenceResult`. Its immutable detail preserves the previous and
latest snapshot context, exact prices, signed deltas, comparison kinds,
canonical listing and release-change order, unchanged and incomparable counts,
and diagnostics. Listing identities remain `(release_id, listing_id)`;
release-level detail is limited to supplied lowest and highest price facts. The
presentation service and builder do not select history, compare values,
calculate deltas, convert currencies, classify or sort changes. If no result is
supplied, the sixth destination remains visible with an unavailable state.

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

## Desktop navigation

The Dashboard's **Open Collection Explorer** action opens Overview in a
twelve-tab, scrollable window. The window retains the homepage model that was
current when it opened. The action is disabled while that model is loading or
stale.

Weekend Listings is the fifth tab, Price Changes is the sixth, Supply Changes
is the seventh, Rare Appearances is the eighth, Marketplace Activity is the
ninth, Listing Lifecycle is the tenth, and Marketplace Momentum is the
eleventh, and Marketplace Stability is the twelfth. Opening or selecting them
performs no module execution, Marketplace
fetch, history
query, repository access, persistence write, comparison, sorting, filtering or
refresh; each only renders the result captured when the Explorer was built.

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

## First-slice limitations

Search, filtering, user sorting, charts, forecasting, arbitrary date ranges,
per-release trends, Opportunity,
Protected Records, Market Movers, broader Marketplace Intelligence, automatic
Price Changes, Marketplace Momentum, or Marketplace Stability execution, live Marketplace monitoring,
background refresh, and AI summaries remain future work.
