# Discogs Intelligence Platform — Project Bootstrap

## Purpose

This is the concise onboarding entry point for contributors to the Discogs
Intelligence Platform (DIP). The repository is an architecture-first,
single-user desktop decision-support platform for collectors.

Its governing principle is:

> **Automate the research, not the decision.**

DIP preserves collection and Marketplace evidence, calculates deterministic
and explainable intelligence, and helps the collector decide where to
investigate. It does not automate buying, selling, pricing, or collecting
decisions.

## Current release and development state

**Version 0.5.1 — Marketplace Change Explorer**

DIP v0.5.1 was released on 2 August 2026 and is the latest completed, tagged
public personal-use release. Its annotated tag and GitHub release exist.
Version 0.5 adds the single-collection
Collector Run, canonical Marketplace and Intelligence History integration,
Collector Review, primary desktop session restoration, explicit verified
database backup, safe diagnostics, truthful desktop availability, genuine
v0.4.0 upgrade coverage, and Linux/macOS artifact-validating CI. macOS is the
primary personal-use platform; Linux receives automated headless compatibility
validation, and Windows is not supported.

Version 0.5.1 releases read-only release-level Price and Supply Changes in
Collection Explorer from one compatible canonical Marketplace snapshot pair.
Its released target also includes truthful transactional CSV-import feedback.

Unreleased Results Presentation work distinguishes **Previous snapshot**,
**Latest snapshot**, current catalogue metadata, **Collector Run**, and
**Marketplace Changes** through one closed presentation glossary. Existing
Markdown and Excel outputs are visibly labelled **Legacy Collector Run
analysis** while preserving their legacy calculations and payload values. The
milestone remains unversioned, in progress, and outside v0.5.1.

Project creation/opening UI, Project-scoped refresh, multi-project workflows,
automatic backup, and in-app restore are not implemented. Collection,
Marketplace, intelligence, history, and research data are not yet partitioned
by Project, so the practical workflow remains one collection.

## Implemented architecture

```text
Desktop UI
    ↓
Workspaces
    ↓
Presentation Services
    ↓
Application Services
    ↓
Repository Interfaces
    ↓
Persistence
    ↓
External Providers
```

The composition root assembles concrete dependencies. Workspaces and renderers
remain presentation-only; application services orchestrate use cases;
repositories preserve storage boundaries; intelligence modules remain
deterministic, versioned, and independent of SQLite and UI frameworks.

## Authoritative reading

Before changing the repository, read:

- [AGENTS.md](AGENTS.md);
- [Vision](docs/Vision.md);
- [Architecture](docs/Architecture.md);
- [Roadmap](docs/Roadmap.md);
- [Development Standard](docs/Development/DevelopmentStandard.md);
- [AI Development Playbook](docs/Development/AI_Development_Playbook.md).

Then read the architecture document for the area being changed, including
[Project Workspace](docs/ProjectWorkspace.md),
[Marketplace Architecture](docs/MarketplaceArchitecture.md),
[Portfolio Intelligence](docs/PortfolioIntelligence.md), or
[Intelligence History](docs/IntelligenceHistory.md) as applicable.

## Sources of truth

Use the implementation and its tests to establish current behaviour. Use
release tags and Git history to establish released scope and dates. Current
architecture and roadmap documents explain boundaries and product direction;
proposal documents do not prove that a feature exists.

Inspect the branch and working tree before editing. Keep changes focused,
preserve deterministic ordering and immutable boundaries, run the full test
suite and compilation, run `git diff --check`, inspect the final diff, and do
not commit unless explicitly asked.
