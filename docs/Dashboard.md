# Interactive Dashboard

## Purpose

The Version 0.2 Interactive Dashboard is a read-only presentation layer for
results produced by the Collection Intelligence Engine.

The dashboard does not calculate intelligence. It converts standard
`IntelligenceResult` objects into immutable, presentation-neutral view models
that can later be rendered by the desktop application or another interface.

---

# First Vertical Slice

The first dashboard vertical slice supports one card only:

- Collection Health

Hidden Gems, Market Movers and other future intelligence cards are outside the
scope of this slice.

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
CollectionHealthModule
        ↓
IntelligenceResult
        ↓
CollectionHealthCardPresenter
        ↓
DashboardCardViewModel
        ↓
Future desktop or web renderer
```

The presenter receives an already calculated result. It may validate and
select presentation fields, but it must not recalculate the overall or
component scores.

---

# Dashboard View Models

`IntelligenceDashboardViewModel` contains an immutable tuple of intelligence
cards. Each `DashboardCardViewModel` exposes:

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

---

# Safe Card States

| State | Meaning | Presentation behaviour |
|---|---|---|
| `ready` | Required completed metrics are available | Display the full card |
| `skipped` | Analysis could not meaningfully run | Display guidance and available zero-state evidence |
| `failed` | The engine isolated a module failure | Display the failure summary and diagnostics without a score |
| `incomplete` | A completed result lacks required valid card metrics | Display available fields and an explicit incomplete diagnostic |

Scores must be finite values between 0 and 100. Invalid or missing values are
not guessed, clamped or recalculated.

---

# Desktop Integration

This slice deliberately does not modify the existing Tkinter dashboard. The
current desktop behaviour remains unchanged while the presentation contract is
tested independently.

A future integration task can render these view models in Tkinter without
moving scoring or engine logic into the user interface.
