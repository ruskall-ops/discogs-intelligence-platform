# Collection Explorer

## Purpose

The first unified Collection Explorer is the primary desktop workspace for
detailed Collection Intelligence. It orients the user with a concise Overview
and provides navigation to the established Collection Health and Hidden Gems
detail experiences.

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

The application service passes the exact same homepage model to both detail
services and builds the Explorer once when the window opens. Switching tabs
does not query history, execute intelligence, or rebuild the workspace.

The older current-engine Explorer presenter remains available as a compatibility
boundary, but the desktop application no longer uses it or executes that second
pipeline.

## Destinations

Destinations use stable identifiers and always appear in this explicit order:

1. Overview;
2. Collection Health;
3. Hidden Gems.

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

## States and degradation

The Explorer and destinations use explicit `loading`, `available`, `partial`,
`empty`, `unavailable`, and `error` states. A usable Overview with one missing
detail destination is partial rather than failed. Empty Intelligence History
produces an empty Overview and stable unavailable detail destinations.
Unexpected consistency errors continue to the desktop error boundary.

## Desktop navigation

The Dashboard's **Open Collection Explorer** action opens Overview in a
three-tab, scrollable window. The window retains the homepage model that was
current when it opened. The action is disabled while that model is loading or
stale.

The existing direct **Open Collection Health** and **Open Hidden Gems** actions
remain dedicated windows for compatibility and convenience. They share the
same presentation services, immutable detail models, and renderer instances as
the Explorer, so they do not maintain separate detail implementations.

## First-slice limitations

Search, filtering, user sorting, charts, historical trends, Opportunity,
Weekend Listings, Protected Records, Market Movers, Marketplace Intelligence,
background refresh, and AI summaries remain future work.
