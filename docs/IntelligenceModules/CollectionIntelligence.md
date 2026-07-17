# Collection Intelligence

## Purpose

The Collection Intelligence subsystem is the analytical heart of the Discogs Intelligence Platform (DIP).

Its purpose is to transform collection, marketplace and historical data into meaningful, explainable intelligence that helps collectors better understand their collections and make informed decisions.

Unlike data management, which stores and retrieves information, Collection Intelligence is responsible for interpreting that information and presenting actionable insights.

---

# Design Philosophy

Collection Intelligence is guided by five core principles.

## Explainable Intelligence

Every conclusion should be understandable.

Users should always be able to answer:

- What was identified?
- Why was it identified?
- What evidence supports it?
- How confident is the conclusion?

Opaque scoring systems should be avoided wherever possible.

---

## Intelligence, Not Automation

The platform automates research rather than decisions.

Collection Intelligence may identify opportunities, highlight risks or surface trends, but users remain responsible for all collection decisions.

The subsystem never recommends buying or selling as an automatic action.

---

## Modular Analysis

Every intelligence capability should exist as an independent module.

Examples include:

- Collection Health
- Hidden Gems
- Market Movers
- Collection Trends
- Weekly Intelligence Reports
- Future Recommendation Engines

Modules should be reusable throughout the platform.

---

## Historical First

Current data is useful.

Historical context creates intelligence.

Collection Intelligence should always leverage historical snapshots wherever meaningful comparisons improve understanding.

---

## Presentation Independent

Collection Intelligence should never contain user interface logic.

Its outputs should be equally usable by:

- Dashboard
- Collection Explorer
- Weekly Reports
- Future Mobile Applications
- Future AI Collection Assistant
- APIs

---

# Responsibilities

The Collection Intelligence subsystem is responsible for:

- analysing collection data
- analysing marketplace information
- comparing historical snapshots
- generating explainable insights
- identifying trends
- identifying opportunities
- identifying risks
- producing reusable intelligence results

It is not responsible for:

- importing data
- rendering user interfaces
- generating Markdown
- managing configuration
- storing marketplace information
- making user decisions

---

# Collection Intelligence Engine

The Collection Intelligence Engine coordinates every intelligence module.

It provides a consistent execution environment while ensuring every module produces explainable, reusable results.

```
Collection Data
Marketplace Data
Historical Snapshots
User Context
        │
        ▼
Collection Intelligence Engine
        │
        ├── Collection Health
        ├── Hidden Gems
        ├── Market Movers
        ├── Collection Trends
        └── Future Modules
        │
        ▼
Standard Intelligence Results
```

The engine is responsible for:

- preparing analysis context
- executing intelligence modules
- validating outputs
- collecting diagnostics
- recording analysis results
- exposing intelligence consistently throughout the platform

---

# Version 0.2 Engine Foundation

The initial Collection Intelligence Engine foundation is implemented in
`src/dip/intelligence/`.

The foundation provides:

- a runtime-checkable `IntelligenceModule` protocol;
- an ordered `IntelligenceRegistry` with unique module identifiers;
- a prepared `IntelligenceContext` shared by all modules;
- standard `IntelligenceResult` and `IntelligenceExecution` models;
- deterministic registry-order execution;
- validation of module outputs;
- failure isolation so one module cannot terminate the full analysis;
- aggregate completion, failure and skipped counts;
- compatibility with the original tuple-returning engine API.

The engine does not yet connect to the desktop interface or replace the
existing opportunity-scoring workflow. This deliberately preserves Version
0.1 application behaviour while Version 0.2 modules are developed and tested.

## Module Contract

Each module declares a stable identifier and version, then analyses only the
prepared context supplied by the engine:

```python
class CollectionHealthModule:
    module_id = "collection_health"
    module_version = "1.0"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=self.module_id,
            status="completed",
            summary="Collection health analysis completed.",
        )
```

Module identifiers must be unique. Registration fails immediately when an
identifier is empty, duplicated, missing a version or missing `analyse()`.

## Failure Isolation

The engine executes modules independently in registry order. If a module
raises an exception or returns an invalid result:

1. the engine creates a failed `IntelligenceResult` for that module;
2. a concise diagnostic records the failure type and message;
3. the next registered module still executes;
4. the overall execution reports the completed and failed counts.

The engine catches ordinary module exceptions, but it does not intercept
process-level signals such as keyboard interruption or system exit.

---

# Analysis Context

Every intelligence module should receive a consistent analysis context.

Rather than directly querying the database, modules operate on a prepared snapshot containing the information required for that analysis.

Typical context includes:

- current collection
- marketplace information
- historical snapshots
- user preferences
- active filters
- analysis run information

The implemented context currently exposes collection records, marketplace
data, historical snapshots, user context, active filters, analysis run ID and
capture time. Modules should treat this prepared evidence as read-only.

This keeps modules deterministic, testable and independent.

---

# Intelligence Modules

Each intelligence capability is implemented as a separate module.

Modules should be:

- independent
- reusable
- testable
- versioned

Every module should declare:

- its purpose
- required data
- expected outputs
- dependencies (where unavoidable)

Examples include:

| Module | Purpose |
|----------|----------|
| Collection Health | Overall collection analysis |
| Hidden Gems | Under-recognised releases |
| Market Movers | Significant marketplace changes |
| Collection Trends | Long-term historical analysis |
| Weekly Report | Summary of recent intelligence |

Future versions may introduce:

- Recommendation Engine
- Collector Profile
- Demand Analysis
- Dealer Toolkit

---

# Intelligence Results

Every module should return a consistent result structure.

A standard result should contain:

- module identifier
- execution status
- summary
- insights
- metrics
- supporting evidence
- diagnostics
- module version

This allows every presentation layer to consume intelligence without requiring module-specific logic.

The execution wrapper also exposes module totals and result lookup by stable
module identifier, allowing future dashboards and reports to consume the same
engine output without recalculating intelligence.

---

# Explainability

Explainability is a fundamental architectural requirement.

Every significant conclusion should include:

- supporting evidence
- reasoning
- confidence
- limitations

For example:

Instead of:

> Hidden Gem Score: 87

The platform should explain:

> This release has been identified because marketplace supply is unusually low, recent sale prices have increased, and demand has remained consistent across recent snapshots.

The goal is to build user trust through transparency.

---

# Historical Intelligence

Historical snapshots transform static information into intelligence.

Rather than only answering:

> What does my collection look like?

Collection Intelligence should answer:

- What changed?
- Why did it change?
- What trends are emerging?
- What deserves attention?

Historical analysis underpins:

- Market Movers
- Collection Trends
- Weekly Reports
- Future Recommendation Engines

---

# Reusable Intelligence

Collection Intelligence should generate reusable outputs.

The same intelligence should power multiple experiences.

For example:

```
Collection Health
        │
        ├── Dashboard
        ├── Collection Explorer
        ├── Weekly Report
        └── AI Assistant
```

Intelligence should never be recalculated independently for different presentation layers.

---

# Extensibility

The subsystem is designed for continuous expansion.

New intelligence modules should integrate without requiring changes to existing modules.

Examples of future modules include:

- Portfolio Diversification
- Collection Risk Analysis
- Collection Goals
- Investment Performance
- Dealer Insights
- AI Collection Assistant

The engine should remain stable while individual modules evolve independently.

---

# Relationship to Other Documentation

| Document | Purpose |
|----------|----------|
| PlatformArchitecture.md | Overall platform architecture |
| Architecture.md | Software implementation |
| Database.md | Data model |
| ReportingEngine.md | Reporting architecture |
| Roadmap.md | Planned intelligence modules |

---

# Guiding Principle

Collection Intelligence exists to transform data into explainable understanding.

Every module should help users answer three questions:

1. What is happening?
2. Why is it happening?
3. What should I investigate next?

The subsystem should never replace the collector's judgement.

Its role is to provide the highest quality intelligence possible while ensuring every conclusion remains transparent, reproducible and understandable.
