# Collection Explorer

## Purpose

The first unified Collection Explorer is the primary desktop workspace for
detailed Collection Intelligence. It orients the user with a concise Overview,
provides the established Collection Health and Hidden Gems details, and shows a
neutral recent Collection Trends comparison and factual Weekend Listings from
an explicitly supplied Marketplace Intelligence result.

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
already-produced Weekend Listings result is supplied at the same presentation
boundary. Switching tabs does not query history, execute intelligence, fetch
Marketplace data, or rebuild the workspace.

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
5. Weekend Listings.

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

## States and degradation

The Explorer and destinations use explicit `loading`, `available`, `partial`,
`empty`, `unavailable`, `insufficient_history`, `insufficient_data`, and `error`
states. A usable
Overview with one missing detail destination is partial rather than failed.
Empty Intelligence History produces an empty Overview and stable unavailable
detail destinations. Unexpected consistency errors continue to the desktop
error boundary. A missing Weekend Listings result is unavailable without
degrading otherwise usable collection destinations. A partial Weekend source
keeps the Explorer usable and marks the aggregate workspace partial.

## Desktop navigation

The Dashboard's **Open Collection Explorer** action opens Overview in a
five-tab, scrollable window. The window retains the homepage model that was
current when it opened. The action is disabled while that model is loading or
stale.

Weekend Listings is the fifth tab. Opening or selecting it performs no module
execution, Marketplace fetch, repository access, persistence write, sorting,
filtering, or refresh; it only renders the result captured when the Explorer
was built.

The existing direct **Open Collection Health** and **Open Hidden Gems** actions
remain dedicated windows for compatibility and convenience. They share the
same presentation services, immutable detail models, and renderer instances as
the Explorer, so they do not maintain separate detail implementations.

## First-slice limitations

Search, filtering, user sorting, charts, forecasting, arbitrary date ranges,
per-release trends, Opportunity,
Protected Records, Market Movers, broader Marketplace Intelligence, live
Marketplace monitoring, background refresh, and AI summaries remain future
work.
