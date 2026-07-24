# Decision Intelligence

## Purpose

Decision Intelligence is the third intelligence layer within the Discogs Intelligence Platform.

Its purpose is to transform existing deterministic intelligence into transparent, explainable assessments without introducing recommendations, predictions, or opaque scoring.

Decision Intelligence exists to answer questions such as:

- What do these historical facts collectively indicate?
- How consistent are the observed signals?
- How strong is the supporting evidence?
- How should multiple intelligence modules be interpreted together?

Decision Intelligence does **not** answer:

- Should I buy this release?
- Will the price increase?
- Is this guaranteed to be rare?
- What investment return should I expect?

Those questions require subjective judgement beyond the scope of deterministic intelligence.

---

# Architectural Position

```text
Marketplace Retrieval
        │
        ▼
Marketplace History
        │
        ▼
──────────────────────────────────────
Primary Intelligence
──────────────────────────────────────

Price Changes

Supply Changes

Rare Appearances

Listing Lifecycle

Weekend Listings

        │
        ▼
──────────────────────────────────────
Composite Intelligence
──────────────────────────────────────

Marketplace Activity

        │
        ▼
──────────────────────────────────────
Decision Intelligence
──────────────────────────────────────

Marketplace Momentum

Marketplace Stability

Marketplace Scarcity

Marketplace Opportunity

        │
        ▼
Presentation
```

---

# Intelligence Layers

## Primary Intelligence

Primary Intelligence derives individual deterministic facts directly from Marketplace History.

Examples include:

- Price Changes
- Supply Changes
- Rare Appearances
- Listing Lifecycle
- Weekend Listings

Primary Intelligence owns historical analysis.

It is the only intelligence layer permitted to analyse Marketplace History directly.

---

## Composite Intelligence

Composite Intelligence combines existing factual intelligence.

It does not perform historical analysis.

It does not reinterpret history.

It aggregates deterministic facts already owned by Primary Intelligence.

Example:

- Marketplace Activity

---

## Decision Intelligence

Decision Intelligence interprets existing intelligence outputs using explicit deterministic rules.

It never analyses Marketplace History.

It never duplicates Primary Intelligence.

It never duplicates Composite Intelligence.

Decision Intelligence transforms factual intelligence into structured assessments.

Its release-level Marketplace outputs may feed Portfolio Intelligence.
Portfolio Intelligence is a distinct aggregation layer: it combines ownership
facts with already-produced Decision Intelligence and does not reinterpret
Marketplace History. Portfolio Overview 1.0 consumes Marketplace Opportunity
only. Portfolio Decision Intelligence, which would interpret portfolio-level
facts, is deferred. See `PortfolioIntelligence.md`.

Portfolio Concentration's per-dimension mathematical states remain descriptive
Portfolio Intelligence. They measure normalized category clustering and are not
Decision Intelligence, investment-risk assessments, or recommendations.

---

# Design Principles

Every Decision Intelligence module must satisfy the following principles.

## Explainable

Every assessment must be reconstructable.

Users must be able to determine exactly why an assessment was produced.

No hidden calculations.

No unexplained weighting.

---

## Deterministic

The same inputs must always produce the same outputs.

Decision Intelligence must never rely on:

- randomness
- machine learning
- probabilistic models
- external services
- current timestamps
- user state

---

## Transparent

Every contributing component must remain visible.

Example:

Marketplace Momentum exposes:

- Price Direction
- Supply Direction
- Activity Intensity
- Evidence Coverage

rather than only exposing:

```
Momentum = Positive
```

---

## Immutable

Decision Intelligence outputs are immutable.

All outputs must use frozen dataclasses consistent with the platform architecture.

---

## Versioned

Decision rules evolve independently from module versions.

Every Decision Intelligence module must expose:

- Module Version
- Rule Set Version

Changing rule behaviour must not require changing serialization.

---

# Inputs

Decision Intelligence consumes `IntelligenceResult` outputs.

It must never consume:

- Marketplace History
- Marketplace snapshots
- repositories
- SQLite
- APIs
- network clients

Execution services are responsible for gathering intelligence.

Domain modules are responsible only for interpretation.

---

# Source Ownership

Decision Intelligence never owns historical facts.

Historical facts remain owned by the originating intelligence module.

For example:

| Historical Fact | Owned By |
|-----------------|----------|
| Price direction | Price Changes |
| Supply direction | Supply Changes |
| Appearance history | Rare Appearances |
| Listing persistence | Listing Lifecycle |
| Marketplace activity | Marketplace Activity |

Decision Intelligence only interprets those facts.

---

# Evidence Coverage

Decision Intelligence reports evidence quality.

Evidence Coverage is **not** confidence.

Evidence Coverage is **not** probability.

It simply describes the completeness and compatibility of the available intelligence.

Suggested values:

- Complete
- Partial
- Limited
- Insufficient

Coverage must be calculated deterministically.

---

# Diagnostics

Decision Intelligence preserves diagnostics from source intelligence.

Additional diagnostics may be added only for Decision Intelligence concerns.

Examples include:

- Missing required intelligence
- Incompatible source histories
- Unsupported source versions
- Duplicate source results
- Malformed outputs

Diagnostics must remain factual.

---

# Provenance

Every assessment must preserve provenance.

Users must be able to determine:

- Which intelligence modules contributed
- Which module versions were used
- Which rule set produced the assessment

Decision Intelligence must never hide its evidence.

---

# Component-Based Assessments

Decision Intelligence should favour multiple visible components over a single opaque score.

Preferred:

```
Momentum

Price Direction        Positive

Supply Direction       Neutral

Activity               High

Evidence               Complete

Assessment             Positive
```

Avoid:

```
Momentum Score

82.7
```

Opaque scores are difficult to explain, validate, and evolve.

---

# Recommendations

Decision Intelligence must not recommend actions.

Prohibited examples:

- Buy
- Sell
- Hold
- Strong Buy
- Excellent Investment
- Avoid
- High Return Expected

Decision Intelligence describes observed conditions.

It does not prescribe decisions.

---

# Forecasting

Decision Intelligence does not predict future behaviour.

Examples of prohibited outputs include:

- likely to increase
- expected to fall
- probable sale
- guaranteed appreciation
- investment return forecast

Historical observations must not be presented as predictions.

---

# Execution Model

## Marketplace Stability

Marketplace Stability is the second Decision Intelligence module. Momentum
describes the direction of supplied observed change; Stability describes the
consistency or changeability of supplied observed conditions. Neither dimension
is a recommendation or forecast.

Version `1.0` requires already-produced Marketplace Activity and Listing
Lifecycle results. Price Changes, Supply Changes, Rare Appearances, and
Marketplace Momentum are optional. Momentum is preserved only as factual
context and cannot alter the Stability assessment.

The application execution service obtains each configured result once,
validates module versions and coherent analyzed-history provenance, constructs
immutable release and listing facts, and explicitly executes the Stability
module once. The domain receives no Marketplace snapshots, history services,
repositories, persistence adapters, network clients, or engines.

Four visible components determine the release-level result:

- price-change stability uses Activity's historical price-change count;
- supply-change stability uses Activity's historical supply-change count;
- appearance continuity uses Activity's exact Decimal appearance ratio and
  longest internal absence;
- listing persistence aggregates supplied Lifecycle states and transition
  counts by `release_id` without reconstructing presence sequences.

The default price and supply bands classify zero changes as `stable`, one or
two as `mixed`, and three or more as `volatile`. Appearance continuity is
stable only for ratio one and zero internal absence; the configurable mixed
absence maximum defaults to one. Listing persistence exposes state counts,
transition totals, and exact Decimal ratios. Its configurable volatile
disrupted proportion defaults to `0.5`, and its repeated-transition threshold
defaults to two. All thresholds are immutable, validated, and preserved in the
typed output.

Evidence coverage means availability and compatibility, not confidence or
probability. The assessment evaluates rules in the order insufficient,
volatile, stable, then mixed. It exposes stable, mixed, volatile, and usable
component counts plus canonical reason codes, provenance, diagnostics, module
version `1.0`, and rule-set version `1.0`. Here `volatile` means repeated or
concentrated observed changes only; it makes no financial-risk or future-
behaviour claim.

Marketplace Stability never recommends buying, selling, holding, bidding, or
avoiding a release and never predicts future price, supply, demand, or listing
behaviour.

## Marketplace Scarcity

Marketplace Scarcity is the third Decision Intelligence module. It describes
how limited a release's observed Marketplace availability has been within the
supplied evidence. It does not claim absolute rarity, pressing quantity,
edition size, desirability, investment quality, or future scarcity.

Version `1.0` requires already-produced Rare Appearances and Listing Lifecycle
results. Marketplace Activity, Supply Changes, Marketplace Stability, and
Marketplace Momentum are optional. Stability and Momentum are independent
display context only and cannot alter Scarcity classification.

The application execution service obtains each configured result once,
validates module versions and coherent analyzed-history provenance, and
constructs immutable release and listing facts. The domain receives no
Marketplace snapshots, history services, repositories, persistence adapters,
network clients, or engines.

Scarcity exposes three core components:

- observed availability aggregates supplied Lifecycle states and classifies
  the currently present listing count using configurable `10`, `5`, and `2`
  minimum boundaries;
- appearance scarcity uses Rare Appearances' exact Decimal ratio with default
  boundaries `0.75` and `0.50`;
- listing-persistence scarcity exposes lifecycle-state counts, exact average
  observation and disruption ratios, transition totals, and longest supplied
  absence without reconstructing listing sequences.

Supply context is factual and optional. It never overrides required-source
evidence. Evidence coverage describes availability and compatibility rather
than confidence or probability. Assessment rules evaluate insufficient, very
scarce, scarce, abundant, common, then limited conditions. All thresholds,
components, reason codes, provenance, diagnostics, module version `1.0`, and
rule-set version `1.0` remain visible.

All labels mean observed Marketplace conditions. Scarcity does not infer why a
listing disappeared, that it sold, total production, or availability outside
the analyzed Marketplace evidence. It never recommends or forecasts.

## Marketplace Opportunity synthesis

Marketplace Opportunity is the first synthesis-oriented Decision Intelligence
module. It consumes only already-produced Marketplace Momentum, Marketplace
Stability, and Marketplace Scarcity results. It has no lower-level Marketplace
Intelligence fallback and cannot access history, snapshots, prices, listings,
repositories, persistence, or network clients.

The independent dimensions retain their ownership:

- Momentum describes observed direction;
- Stability describes observed consistency;
- Scarcity describes limited observed Marketplace availability;
- Opportunity synthesizes those supplied dimensions.

The explicit source-state mapping is: positive Momentum and stable Stability
are supportive; mixed or neutral Momentum and mixed Stability are neutral;
negative Momentum is adverse; volatile Stability is limiting; scarce and very
scarce availability are supportive scarcity context; limited availability is
neutral; and common or abundant availability is limiting. Insufficient source
states are unusable.

Version `1.0` evaluates rules in this canonical order: insufficient, strong,
weak, constrained, developing, then balanced. Strong alignment requires
complete evidence, positive Momentum, stable Stability, and scarce or very
scarce observed availability. Volatility, common or abundant availability, and
limited evidence constrain synthesis. Negative direction combined with
limiting dimensions produces weak alignment. Usable mixed combinations are
balanced.

The output preserves every source assessment, every source evidence state,
its mapped category, category counts, canonical reason codes, provenance,
diagnostics, module version `1.0`, and rule-set version `1.0`. There are no
points, percentages, weights, scores, price targets, value claims, forecasts,
or recommendations. Opportunity means an observed Marketplace evidence
synthesis, not financial advice.

Execution services coordinate Decision Intelligence.

Execution services:

- Obtain required `IntelligenceResult` objects
- Validate compatibility
- Validate provenance
- Build immutable inputs
- Execute one Decision Intelligence module

Decision Intelligence modules must never execute other modules.

---

# Presentation

Presentation layers must never alter Decision Intelligence.

Presentation may:

- Map immutable outputs
- Format values
- Display diagnostics

Presentation must never:

- Calculate assessments
- Apply rules
- Aggregate results
- Reorder data

---

# Rule Evolution

Decision Intelligence rules are expected to evolve.

Rule changes should remain:

- Explicit
- Documented
- Deterministic
- Versioned

Older Intelligence History records must remain reproducible.

---

# Future Decision Intelligence Modules

## Portfolio Opportunity Alignment 1.0

Portfolio Opportunity Alignment is the first Portfolio Decision Intelligence
module. It consumes exactly the already-produced Portfolio Overview,
Distribution, and Concentration 1.0 outputs. Overview owns holdings-to-
Marketplace-Opportunity association, Distribution owns category membership,
and Concentration owns mathematical metrics and states; Alignment only
interprets their relationship.

The application boundary calls each configured provider once and validates
typed outputs, statuses, versions, ownership and release populations, snapshot
identity, supported dimensions, and Concentration's reference to the supplied
Distribution result. Invalid or incompatible sources produce deterministic
`insufficient` synthesis without a lower-level fallback.

Opportunity maps in canonical order to supportive (`strong`, `developing`),
neutral (`balanced`), limiting (`constrained`), adverse (`weak`), and unusable
(`insufficient`, unmatched, or missing). Release/copy numerators, denominators,
Decimal shares, IDs, source category order, dominant-category order, and
separate release/copy concentration states remain visible.

Assessment precedence is `insufficient`, `constrained`, `broadly_aligned`,
`selectively_aligned`, then `mixed`. Versioned thresholds, source evidence,
reasons, diagnostics, and provenance are inspectable. The module creates no
weighted score, forecast, valuation, recommendation, or rebalancing guidance.

Potential Decision Intelligence modules include:

- Marketplace Momentum
- Marketplace Stability
- Marketplace Scarcity
- Marketplace Opportunity
- Portfolio Risk
- Portfolio Diversification
- Portfolio Quality
- Collection Priority

All future modules should follow the architectural principles defined in this document.

---

# Prohibited Patterns

Decision Intelligence must never:

- Access Marketplace History
- Analyse Marketplace snapshots
- Access repositories
- Access SQLite
- Access network services
- Duplicate Primary Intelligence
- Duplicate Composite Intelligence
- Perform hidden weighting
- Generate opaque scores
- Use machine learning
- Use probabilistic confidence
- Forecast prices
- Recommend investments
- Mutate `IntelligenceResult` outputs

---

# Guiding Principle

> **Primary Intelligence discovers facts. Composite Intelligence organises facts. Decision Intelligence interprets facts. The user makes the decision.**
## Relationship to Historical Intelligence

Intelligence Change Analysis 1.0 compares two completed Portfolio Opportunity
Alignment 1.0 results without rerunning or reinterpreting Alignment.
Assessment and evidence changes are categorical modifications; release, copy,
and ratio changes are objective numeric deltas. No transition states
desirability or recommends an action.
