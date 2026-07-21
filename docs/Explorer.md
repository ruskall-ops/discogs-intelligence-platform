# Collection Intelligence Explorer

## Purpose

The Version 0.2 Collection Intelligence Explorer provides desktop drill-down
views for Collection Health, Hidden Gems and Historical Intelligence. It helps
users inspect intelligence already produced by the Collection Intelligence
Engine; it creates no intelligence and makes no collection decisions.

## Architecture

The Explorer extends the existing dashboard presentation pipeline:

```text
IntelligenceResult
        ↓
Dashboard presenters
        ↓
Immutable dashboard presentation models
        ↓
CollectionIntelligenceExplorerPresenter
        ↓
Immutable Explorer section models
        ↓
DesktopExplorerRenderer
        ↓
Tkinter Explorer window
```

The Explorer receives only dashboard presentation models. It does not import
intelligence modules, access SQLite, query Discogs or manipulate snapshots.
The dashboard models retain full presentation-safe release lists for drill-down
while the compact dashboard cards continue to show at most five releases.

## Sections

### Collection Health

Displays the module-provided overall health, summary, named component scores,
evidence and diagnostics. It does not reproduce component or overall scoring.

### Hidden Gems

Displays the total candidate count and all ranked presentation-safe releases
returned by the module. Each release includes artist, title, explanation and
supporting evidence. Raw Hidden Gem scores, component factors and weights are
not exposed.

### Historical Intelligence

Displays the latest and previous snapshots, collection-size and valuation
changes, additions, removals, gainers, decliners, evidence coverage and
diagnostics. Addition and removal identities are displayed separately from
valuation movements. Fewer than two comparable snapshots remains an
informational insufficient-history state.

## Navigation and rendering

The existing dashboard includes one **Open Collection Intelligence Explorer**
button. It opens a lightweight Tkinter window with three tabs and scrollable,
read-only text. No routing framework or desktop redesign is introduced.

Presentation mapping and desktop text rendering remain separate. A small
navigation controller converts the current dashboard view model into a
rendered Explorer view before Tkinter creates widgets.

## Resilience

Every section independently preserves the dashboard state:

- ready;
- unavailable;
- failed;
- skipped;
- incomplete;
- insufficient history.

A missing, malformed or failed section cannot prevent the other sections from
mapping or rendering.

## Version 0.2 limitations

The Explorer does not implement charts, graphs, search, filtering, sorting,
custom historical ranges, marketplace intelligence, recommendations,
persistence changes or new intelligence modules.
