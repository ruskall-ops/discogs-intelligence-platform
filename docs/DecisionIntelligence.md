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