# Interactive Dashboard

## Purpose

The Version 0.2 Interactive Dashboard is a read-only presentation layer for
results produced by the Collection Intelligence Engine.

The dashboard does not calculate intelligence. It converts standard
`IntelligenceResult` objects into immutable, presentation-neutral view models
that can later be rendered by the desktop application or another interface.

---

# Version 0.2 Dashboard Integration

The dashboard now exposes three independent cards:

- Collection Health;
- Hidden Gems;
- Historical Intelligence.

The desktop composition root prepares an `IntelligenceContext`, runs the
existing Collection Intelligence Engine and supplies its standard results to
the dashboard presenter. No intelligence is calculated in the dashboard.

The implementation is located in:

```text
src/dip/experience/dashboard/
├── models.py
└── presenter.py
```

---

# Data Flow

```text
IntelligenceContext
        ↓
Collection Intelligence Engine
        ↓
IntelligenceResult
        ↓
Module-specific card presenter
        ↓
Immutable dashboard view model
        ↓
Desktop dashboard renderer
```

The presenter receives an already calculated result. It may validate and
select presentation fields, but it must not recalculate the overall or
component scores.

---

# Dashboard View Models

`IntelligenceDashboardViewModel` contains an immutable tuple of three
presentation-specific cards. Collection Health continues to use
`DashboardCardViewModel`; Hidden Gems and Historical Intelligence use their
own lightweight immutable view models so internal intelligence models are not
passed into Tkinter.

- module identifier;
- card title and state;
- headline label and score;
- summary;
- named component scores;
- strengths;
- improvement opportunities;
- evidence;
- diagnostics.

The view models contain no Tkinter widgets, database connections, provider
clients or scoring rules.

---

# Collection Health Card

The Collection Health card consumes the standard result returned by
`CollectionHealthModule` and displays:

- overall health score;
- concise summary;
- metadata completeness;
- marketplace coverage;
- confidence-adjusted demand strength;
- valuation coverage;
- identifiable strengths;
- improvement opportunities;
- evidence coverage and diagnostics.

The presenter copies validated values from `IntelligenceResult.metrics`. It
does not import the Collection Health module or reproduce its weighted formula.

# Hidden Gems Card

The Hidden Gems card displays the candidate total and up to five ranked
releases. Each displayed release includes a concise explanation selected from
the module-provided evidence. Internal factors, weights and raw candidate
scores are not exposed to the desktop UI.

# Historical Intelligence Card

The historical card displays snapshot dates, additions, removals,
collection-size change, total/average/median value changes, up to five gainers
and decliners, and valuation evidence counts. A skipped historical result is
presented as insufficient history rather than an error.

---

# Safe Card States

| State | Meaning | Presentation behaviour |
|---|---|---|
| `ready` | Required completed metrics are available | Display the full card |
| `skipped` | Analysis could not meaningfully run | Display guidance and available zero-state evidence |
| `failed` | The engine isolated a module failure | Display the failure summary and diagnostics without a score |
| `incomplete` | A completed result lacks required valid card metrics | Display available fields and an explicit incomplete diagnostic |
| `unavailable` | No module result was supplied | Keep the card visible with a neutral message |
| `insufficient_history` | Fewer than two comparable snapshots exist | Display an informational history message |

Scores must be finite values between 0 and 100. Invalid or missing values are
not guessed, clamped or recalculated.

---

# Desktop Integration

The Tkinter dashboard renders all three cards beneath the existing KPIs.
Application orchestration prepares current collection, latest marketplace and
two-run historical evidence through existing repository reads. The dashboard
package itself receives only engine results and has no persistence or provider
dependency.

Every module result and card mapping is isolated. A failed, missing or
malformed result changes only its own card. The Version 0.2 Collection
Intelligence Explorer now provides read-only drill-down from these card models;
charts, filters and arbitrary ranges remain outside the dashboard.

---

# Version 0.2 Dashboard Homepage

The first Dashboard homepage is a read-only presentation and integration
boundary over completed Intelligence History. It does not run intelligence,
query SQLite, compare executions or rank candidates.

```text
IntelligenceHistoryQueryService     ComparisonPresentationService
                │                               │
                └───────────────┬───────────────┘
                                ▼
                 DashboardHomepageService
                                ▼
              DashboardHomepageViewModelBuilder
                                ▼
                     Desktop Dashboard UI
```

The immutable homepage contains exactly five sections in this order:

1. Collection overview;
2. Collection Health;
3. Hidden Gems;
4. What Changed;
5. Latest execution.

Collection Health and Hidden Gems reuse their established card presenters.
Their calculated scores, counts and ranked candidate order are copied from the
latest completed historical execution. The homepage neither recalculates a
score nor re-ranks a candidate. Hidden Gems displays at most the first three
candidates in the supplied order.

What Changed consumes the existing comparison ViewModel. Changed, unchanged,
added and removed counts are preserved, and non-unchanged modules retain the
order supplied by the comparison boundary. Empty history and a single
execution are normal states; the latter is shown as insufficient history rather
than an error.

Every section has an explicit typed state: `loading`, `available`, `empty`,
`unavailable`, `error` or `insufficient_history`. Missing optional module data
degrades only its corresponding section. The expected comparison-availability
error for fewer than two executions becomes `insufficient_history`; malformed
history, inconsistent ViewModels and unexpected programming failures continue
to propagate to the desktop error boundary.

Filtering, drill-down, charts, multi-run trends and background refresh remain
future work and are not implemented by this homepage slice.
