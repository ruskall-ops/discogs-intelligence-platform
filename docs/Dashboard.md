# Dashboard

## Current desktop availability

Collection summaries, What Changed, Collection Health, Hidden Gems, and
Collection Explorer navigation use real production history and remain enabled,
including truthful empty and insufficient-history states.

The command-centre Portfolio, Opportunity, secondary History, Marketplace, and
Research cards remain visible but disabled as **Not available in this
release**. Their presentation foundations do not yet receive production data.
The former `Portfolio Health` label is `Collection Health` because it presents
the Collection Health result.

## Purpose

The Dashboard is the application's command centre. It retains the Version 0.2
Collection Intelligence cards and homepage, and adds a unified set of
navigation cards over existing Portfolio, Marketplace, Collection, and
Historical presentation state.

The dashboard does not calculate intelligence. Its Collection Intelligence
foundation converts standard `IntelligenceResult` objects into immutable,
presentation-neutral view models. The command centre composes those models
with existing workspace presentation state.

The v0.5.5 primary desktop session may restore Dashboard as the selected
top-level destination after fresh Dashboard queries. It does not persist cards,
counts, observations, comparisons, or other Dashboard presentation models. See
[Session Restoration](SessionRestoration.md).

---

# Collection Intelligence Dashboard foundation

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
Collection Health, Hidden Gems, a latest-two-execution Trends view, Weekend
Listings, and a sixth Price Changes destination. The Marketplace destinations
receive optional, already-produced standard intelligence results when the
Explorer opens; the Dashboard does not select Marketplace History, execute
either module, compare snapshots or fetch Marketplace data. With no supplied
result, the corresponding destination remains visible and unavailable. Charts,
filters and arbitrary ranges remain outside the dashboard.

---

# Collection Intelligence Dashboard homepage

The first Dashboard homepage is a read-only presentation and integration
boundary over completed Intelligence History. It does not run intelligence,
query SQLite, compare executions or rank candidates.

Collector Run is now the production writer for provenance-linked Collection
Intelligence executions. The Dashboard remains a reader through application
query and presentation services; a persisted `SKIPPED` module result is
truthful completed execution evidence, not a partially written History run.

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

Filtering, charts, arbitrary multi-run exploration, and background refresh
remain outside this homepage. Drill-down is provided by the dedicated detail
experiences and Collection Explorer; broader history is presented by the
separate Historical Intelligence experiences.

## Collector Review observations

Each explicit Dashboard refresh requests one immutable
`WeekendObservationWorkspace`. The visible Hot-now count is exactly the number
of projected Hot-now observations in that instance, and its action opens
Collection Review → Observations → Hot now. If observation projection is
unavailable, the card displays an unavailable value and its action is disabled;
the legacy aggregate database count is not used as a fallback.

The established Hidden Gems detail action remains. **Review in Observations**
opens the separate persisted Hidden Gems projection. Dashboard refresh performs
no queue mutation and shares its workspace with the observation renderer for
that refresh cycle, so card count and drill-down cannot disagree.

## Dashboard command centre

The unified Dashboard command centre composes the existing Dashboard homepage,
Portfolio Workspace, Marketplace Workspace, and History Explorer presentation
states. Its deterministic builder exposes eight cards in fixed order:
Portfolio Summary, Collection Health, Opportunity Highlights, Collection
Changes, Historical Changes, Marketplace Highlights, Research Summary, and
Quick Actions.

Each card is built from immutable presentation state. In the production
desktop, only Collection actions dispatch. Portfolio, Opportunity, Historical,
Marketplace, and Research cards remain visible with **Not available in this
release** copy, but their disabled actions do not invoke controllers or open
placeholder windows. Their builders and controllers remain reusable
presentation foundations. No routing framework is introduced.

```text
Presentation Services
        ↓
Workspace builders
        ↓
DashboardCommandCenterBuilder
        ↓
DesktopDashboardCommandCenterRenderer
```

The command centre performs no intelligence execution, history retrieval,
comparison, scoring, aggregation, persistence access, networking, forecasting,
or recommendation. Missing inputs remain visible through the existing
workspace empty and unavailable summaries.

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
