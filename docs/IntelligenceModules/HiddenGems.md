# Hidden Gems Intelligence Module

## Purpose

The Version 0.2 Hidden Gems module surfaces releases already present in a
collection that have an unusual combination of demand, limited supply,
community evidence, ownership context and price efficiency.

It creates a ranked research shortlist. It does not recommend buying, selling
or keeping any record, and it does not execute collection decisions.

---

# Architecture

`HiddenGemsModule` implements the standard `IntelligenceModule` contract. It:

- consumes only a prepared `IntelligenceContext`;
- performs no SQLite or Discogs calls;
- returns a standard `IntelligenceResult`;
- produces immutable `HiddenGemCandidate` objects;
- is registered by `build_v02_intelligence_registry()`;
- has no desktop or dashboard dependency.

The module is implemented in:

```text
src/dip/intelligence/modules/hidden_gems.py
```

---

# Candidate Eligibility

A release must first have valid Wants and current marketplace supply values.
It is eligible for scoring only when:

```text
Wants >= minimum_wants
Copies For Sale <= maximum_marketplace_supply
```

The default thresholds are 25 Wants and no more than 10 marketplace copies.
Both are configurable.

An eligible release becomes a research candidate only when its final score
meets `minimum_hidden_gem_score`, which defaults to 60.

---

# Scoring Philosophy

Hidden Gems uses five independent, named factors. It does not expose only one
opaque score.

| Factor | Default weight | Current evidence |
|---|---:|---|
| Demand | 30% | Wants divided by current marketplace supply |
| Scarcity | 25% | Current supply relative to the configured maximum supply |
| Community rating | 15% | Prepared `community_rating`, when available |
| Collection ownership | 15% | Owned quantity; fewer copies score more highly |
| Price efficiency | 15% | Wants per current lowest-price unit |

Each available factor produces a 0–100 score. The final score is:

```text
Hidden Gem Score =
    Demand Score × demand_weight
  + Scarcity Score × scarcity_weight
  + Community Rating Score × rating_weight
  + Collection Ownership Score × ownership_weight
  + Price Efficiency Score × price_efficiency_weight
```

Missing optional evidence contributes zero for its configured weight. The
module does not redistribute missing weight across the remaining factors, so a
small amount of partial evidence cannot silently receive full confidence.

## Demand

```text
Demand Ratio = Wants / max(Copies For Sale, minimum_supply_divisor)
Demand Score = min(100, Demand Ratio / demand_ratio_for_full_score × 100)
```

## Scarcity

```text
Scarcity Score =
    (1 - Copies For Sale / maximum_marketplace_supply) × 100
```

Supply is bounded by the configured maximum after the eligibility gate.

## Community Rating

```text
Community Rating Score =
    Community Rating / maximum_community_rating × 100
```

No collection rating is substituted when community rating is unavailable.

## Collection Ownership

```text
Ownership Score =
    (maximum_owned_quantity - Owned Quantity)
    / (maximum_owned_quantity - minimum_owned_quantity) × 100
```

If a collection record has no quantity, collection membership is treated as
evidence of one owned copy and this inference is disclosed in diagnostics.

## Price Efficiency

```text
Wants Per Price Unit = Wants / Current Lowest Price
Price Efficiency Score =
    min(100, Wants Per Price Unit
    / wants_per_price_unit_for_full_score × 100)
```

Price efficiency is omitted when no positive current lowest price is present.

---

# Configuration

`HiddenGemsConfig` exposes every scoring threshold and weight:

- `minimum_wants`;
- `maximum_marketplace_supply`;
- `demand_weight`;
- `scarcity_weight`;
- `rating_weight`;
- `ownership_weight`;
- `price_efficiency_weight`;
- `minimum_hidden_gem_score`;
- `demand_ratio_for_full_score`;
- `minimum_supply_divisor`;
- `maximum_community_rating`;
- `minimum_owned_quantity`;
- `maximum_owned_quantity`;
- `wants_per_price_unit_for_full_score`;
- `minimum_price_value`.

Weights must be finite, non-negative and total 1.0. Score thresholds and
normalisation values are validated when the module is created.

---

# Explainability

Every immutable candidate contains:

- release identifier;
- artist and title;
- final Hidden Gem score;
- independent factor scores;
- supporting raw metrics;
- plain-English evidence.

The standard result additionally exposes:

- candidate count;
- highest candidate score;
- average candidate score;
- deterministically ranked candidates;
- eligible and total collection counts;
- configured component weights and candidate threshold;
- aggregate evidence and data-quality diagnostics.

Candidates are ordered by score descending and then release ID ascending, so
identical inputs always produce identical ordering.

---

# Safety and Partial Evidence

- Empty collections return a standard skipped result.
- Missing marketplace rows are counted and disclosed.
- Invalid Wants or supply exclude that release safely.
- Missing or invalid community ratings remove only that factor.
- Missing or invalid prices remove only price efficiency.
- Invalid release identifiers are ignored and counted.
- Ordinary module failures remain isolated by the Collection Intelligence
  Engine.

The current Discogs adapter does not yet prepare community rating or owned
quantity in every collection view. The module therefore treats these as
optional evidence and reports when they are absent or inferred. It does not
invent ratings.

Price efficiency uses the numeric price unit supplied by the current context;
cross-currency comparison is not performed in Version 0.2.

---

# Deliberate Limitations

Version 0.2 does not use:

- historical trends;
- completed-sales frequency;
- price forecasts;
- machine learning;
- recommendation engines;
- personal purchasing advice;
- automatic buying, selling or keeping actions.

The module answers: “Which releases have evidence that makes them worth
researching further?” It does not answer: “What should I do with this record?”

No Hidden Gems dashboard card or desktop integration is included in this
vertical slice.
