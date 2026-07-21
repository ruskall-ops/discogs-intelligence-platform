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
the module-provided evidence. Its shared presentation model also retains the
module-provided score and ordered supporting and factor values for read-only
detail clients; the compact card does not display those additional values.
Weights and scoring rules are not exposed to the desktop UI.

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
malformed result changes only its own card. The Collection Explorer provides
read-only navigation from the current historical homepage into Overview,
Collection Health, Hidden Gems, a latest-two-execution Trends view, and a fifth
Weekend Listings destination. Weekend Listings receives an optional,
already-produced Marketplace Intelligence result when the Explorer opens; the
Dashboard does not execute the module or fetch Marketplace data. With no such
result, the destination remains visible and unavailable. Charts, filters and
arbitrary ranges remain outside the dashboard.

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

---

# Collection Health Experience

The dedicated Collection Health experience is a read-only detail presentation
over the Collection Health card already assembled for the Dashboard homepage.
It does not query history independently, run the Intelligence Engine, or
recalculate any score.

```text
DashboardCollectionHealthViewModel
                │
                ▼
CollectionHealthPresentationService
                │
                ▼
CollectionHealthDetailViewModelBuilder
                │
                ▼
DesktopCollectionHealthController and renderer
                │
                ▼
Collection Health detail window
```

The frozen detail ViewModel preserves the supplied overall score, the four
component scores in canonical module order, strengths, improvement
opportunities, evidence and diagnostics. The renderer displays those values in
the explicit order: component scores, strengths, improvement opportunities,
evidence and diagnostics.

The detail experience supports `loading`, `available`, `empty`, `unavailable`
and `error` states. A skipped empty-collection result retains the module's
existing guidance and zero-valued scores. Missing results remain unavailable;
failed or incomplete results retain available diagnostics and partial values
without guessing missing data.

The Dashboard Collection Health card provides the navigation action. Because
the detail is built from the current homepage ViewModel, the card and detail
window always describe the same historical result. Trends, charts, filtering
and comparisons remain outside this experience.

---

# Hidden Gems Experience

The dedicated Hidden Gems experience is a read-only detail presentation over
the Hidden Gems section already assembled for the Dashboard homepage. Opening
it performs no second history query or Intelligence Engine execution and does
not recalculate qualification or scores.

```text
DashboardHiddenGemsViewModel
                │
                ▼
HiddenGemsPresentationService
                │
                ▼
HiddenGemsDetailViewModelBuilder
                │
                ▼
DesktopHiddenGemsController and renderer
                │
                ▼
Hidden Gems detail window
```

The shared Dashboard model contains both the bounded homepage preview and the
complete candidate tuple. The detail builder copies the complete tuple in its
existing rank order; it never sorts or filters it. Each frozen detail candidate
contains the supplied release identity, display metadata, score, explanation,
evidence, and these explicitly ordered values:

- supporting metrics: wants, copies for sale, demand-to-supply ratio,
  community rating, owned quantity, lowest price, wants per price unit;
- factor scores: demand, scarcity, community rating, collection ownership,
  price efficiency.

The detail experience supports `loading`, `available`, `partial`, `empty`,
`unavailable` and `error`. `partial` is used when a valid candidate contains a
legitimately unavailable optional value, such as rating or price evidence; the
candidate remains in place and the renderer labels that value unavailable.
Aggregate invariants cover rank continuity, unique release and metric IDs,
candidate counts, score ranges and state consistency.

The Dashboard action is shown only when the current Hidden Gems section has
meaningful detail to open. The dedicated window displays the complete list in
a scrollable view. User sorting, filtering, charts, trends, comparisons and
changes to Hidden Gems scoring remain future work.
