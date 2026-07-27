# Platform Architecture

## Purpose

This document provides the product-level view of how the Discogs Intelligence
Platform turns observations into explainable decision support. The canonical
implementation and dependency reference is [Architecture](Architecture.md);
this document does not define a competing software architecture.

## Platform principle

> **Automate the research, not the decision.**

DIP separates source evidence, preserved history, intelligence, presentation,
and user-owned workflow state. A calculated assessment never becomes an
automatic buying, selling, or collection action.

## Conceptual flow

```text
Discogs CSV and Marketplace observations
                    ↓
         Normalisation and persistence
                    ↓
 Collection, Marketplace, and Intelligence History
                    ↓
       Deterministic intelligence layers
                    ↓
           Presentation Services
                    ↓
 Dashboard, Explorers, and Workspaces
                    ↓
          Collector investigation
```

The implementation expresses this through Desktop UI, Workspaces, Presentation
Services, Application Services, Repository Interfaces, Persistence, and
External Providers.

## Evidence layers

### Collection evidence

Collection import and SQLite storage preserve what the collector owns and the
legacy collection-oriented market observations used by the core desktop
workflow.

### Marketplace evidence

Immutable Marketplace snapshots preserve release and listing observations.
Marketplace History is separate from Intelligence History so raw observations
are not confused with conclusions.

### Intelligence

Collection and Marketplace Primary Intelligence calculate factual results.
Composite Intelligence organises already-produced facts. Decision Intelligence
uses explicit versioned rules to describe observed alignment without opaque
scores, recommendations, or forecasts. Portfolio Intelligence aggregates owned
holdings, and Historical Intelligence compares already-calculated results.

### Presentation and workspaces

Presentation Services project completed results into immutable view models.
The production desktop currently wires the Dashboard, Collection Explorer,
Collector Review, and Project Workspace navigation. Portfolio, Marketplace,
and Historical workspace foundations remain visible but are disabled because
the production desktop does not yet supply their completed presentation
models. Workspaces do not calculate intelligence or query persistence.

### User-owned state

Personal collection decisions, Marketplace Research Status, and the durable
Weekend Review Queue remain distinct from objective intelligence. Calculated
Hot-now and Hidden Gems observations enter the queue only through explicit
collector action; their frozen evidence and review notes never alter an
assessment.

## Implemented entry and navigation

Project Workspace is the desktop entry point. Project Management supplies its
active and recent Projects through a storage-independent repository contract.
Normal desktop execution persists those Projects, last-opened order, and active
identity through SQLite. From there, the collector can open the Dashboard
command centre or Portfolio Workspace.

The Dashboard presents production-wired Collection information and What
Changed. Its Portfolio, Opportunity, Historical, Marketplace, and Research
cards remain visible but state that they are not available in this release.
Portfolio, Marketplace, and Historical desktop entry points are disabled.
Collection Review exposes calculated Observations, the Weekend Review Queue,
and the separate Collection Decisions editor.

The primary desktop session safely restores normal window geometry, navigation,
filters, and valid persisted selections. A user-initiated database backup uses
SQLite's supported backup API, independent verification, and atomic
publication. Backup scheduling, retention, and restore remain manual and
outside the application.

## Extensibility

Future data providers and durable research workflows should enter through the
existing provider, application-service, and repository boundaries. Project
creation UI and broader workspace restoration should extend the implemented
Project boundary. The primary desktop session uses Project identity only as a
compatibility guard; see [Session Restoration](SessionRestoration.md).
Alternative interfaces should consume
the same presentation or application boundaries rather than reproducing
intelligence.

Platform Intelligence based on anonymised community data remains a long-term
vision. It is not part of the current single-user desktop architecture.
