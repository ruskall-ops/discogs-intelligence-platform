# Feature Implementation Standard

## Purpose

This document defines the engineering standards for implementing new features within the Discogs Intelligence Platform (DIP).

Every feature should follow these standards unless an Architecture Decision Record (ADR) explicitly documents an exception.

The objective is to ensure the platform remains:

- understandable
- explainable
- deterministic
- maintainable
- extensible

---

# Project Philosophy

The Discogs Intelligence Platform exists to:

> **Automate the research, not the decision.**

The platform provides transparent intelligence that helps users make informed decisions.

It must not:

- recommend purchases
- recommend sales
- execute trades
- make subjective collection decisions

Every intelligence output should explain:

- what was observed
- why it matters
- how the conclusion was reached

---

# Core Engineering Principles

The following principles apply to every feature developed within DIP.

1. Prefer explicit solutions over clever solutions.
2. Prefer deterministic behaviour over hidden behaviour.
3. Prefer composition over duplication.
4. Prefer configuration over hard-coded values.
5. Prefer immutable models where practical.
6. Preserve backwards compatibility whenever possible.
7. Optimise for long-term maintainability rather than short-term convenience.

---

# Architecture Principles

Business logic belongs inside intelligence modules.

Presentation belongs inside the dashboard or future UI.

Persistence belongs inside persistence services.

Provider communication belongs inside data-source adapters.

No architectural layer should bypass another.

All dependencies should flow in one direction.

---

# Intelligence Modules

Every new intelligence capability should implement the standard `IntelligenceModule` contract.

Modules should:

- consume only `IntelligenceContext`
- produce a standard `IntelligenceResult`
- remain deterministic
- remain presentation-independent
- never query SQLite directly
- never query Discogs directly
- never create UI objects

Modules should perform one clearly defined responsibility.

---

# Explainability

Every intelligence calculation should be explainable.

Avoid opaque scores.

Instead expose:

- named factors
- supporting evidence
- diagnostics
- assumptions
- configurable weights

Users should always understand why an output was produced.

---

# Configuration

Avoid magic numbers.

Thresholds, weights and normalisation constants should live inside dedicated configuration objects.

Configuration should:

- be immutable
- validate itself
- expose sensible defaults
- remain overridable

---

# Data Handling

Handle safely:

- empty collections
- missing marketplace data
- invalid values
- partial evidence
- missing optional metrics

The platform should degrade gracefully rather than fail unexpectedly.

Missing optional evidence should never produce fabricated intelligence.

---

# Immutability

Prefer immutable models.

Use frozen dataclasses where practical.

Public result objects should be treated as read-only.

Avoid exposing mutable internal state.

---

# Deterministic Behaviour

Given identical inputs:

- ordering should remain identical
- scores should remain identical
- diagnostics should remain identical

Avoid:

- randomness
- time-dependent calculations
- non-repeatable ordering

---

# Presentation

Presentation layers may:

- format
- validate
- organise
- render

Presentation layers must never:

- calculate intelligence
- reproduce scoring algorithms
- modify intelligence results

---

# Error Handling

Failures should be isolated whenever possible.

Modules should fail independently without preventing unrelated intelligence from executing.

Diagnostics should describe failures rather than hiding them.

---

# Testing Requirements

Every feature should include comprehensive automated tests.

Where applicable test:

- completed execution
- skipped execution
- failed execution
- empty data
- invalid data
- partial evidence
- configuration overrides
- deterministic behaviour
- immutability
- engine integration

Existing tests must continue to pass.

New features should not reduce overall test coverage.

---

# Documentation Requirements

Every feature should update documentation where appropriate.

Typical updates include:

- CHANGELOG
- README
- Roadmap

Major intelligence modules should also receive dedicated documentation under:

```text
docs/IntelligenceModules/
```

Documentation should explain:

- purpose
- architecture
- configuration
- limitations
- future evolution

---

# Feature Scope

Each Pull Request should represent one complete vertical slice.

Avoid combining unrelated features.

Clearly document:

- what is included
- what is intentionally out of scope

Smaller, focused Pull Requests are preferred over large multi-feature submissions.

---

# Versioning

Features should align with the published roadmap.

Avoid introducing future-version functionality into earlier milestones.

Where future functionality is anticipated, document extension points rather than partially implementing them.

---

# Git Workflow

Development follows a feature-branch workflow.

Typical process:

```text
main
 │
 ├── feature/collection-health
 ├── feature/interactive-dashboard
 ├── feature/hidden-gems
 └── ...
```

Each feature should:

1. Branch from `main`.
2. Be implemented independently.
3. Pass all tests.
4. Undergo review.
5. Merge through a Pull Request.

---

# ChatGPT Work Workflow

Development uses ChatGPT Work as an implementation assistant.

Recommended workflow:

1. Design the feature.
2. Produce an implementation brief.
3. Generate the implementation in ChatGPT Work.
4. Download the workspace ZIP.
5. Extract into the local Work directory.
6. Import using:

```bash
./scripts/import-work.sh
```

7. Review the imported changes.
8. Run:

```bash
bash -n scripts/import-work.sh
python3 -m pytest
git diff --check
```

9. Commit.
10. Open a Pull Request.
11. Review.
12. Merge.

---

# Pull Request Checklist

Before opening a Pull Request confirm:

- Feature is complete.
- Tests pass.
- Documentation updated.
- No unrelated changes.
- Existing behaviour preserved.
- Scope matches the implementation brief.
- The implementation follows this standard.

---

# Review Checklist

Every Pull Request should be reviewed against the following criteria.

## Architecture

- Correct separation of concerns
- Appropriate layering
- No unnecessary coupling

## Code Quality

- Readable
- Consistent
- Maintainable
- No duplicated logic

## Intelligence

- Explainable
- Deterministic
- Configurable

## Testing

- Comprehensive
- Existing tests still pass
- Edge cases covered

## Documentation

- Updated
- Accurate
- Matches implementation

---

# Guiding Principle

When multiple solutions exist, prefer the solution that is:

- simpler
- more explicit
- easier to understand
- easier to extend
- easier to test

Avoid unnecessary cleverness.

The objective is not to build the most sophisticated implementation.

The objective is to build the most maintainable platform.

Future contributors should be able to understand every major component with minimal effort.

If a future developer can understand the implementation after reading it once, the design has succeeded.