# AI Development Playbook

## 1. Purpose

This document defines the engineering principles used throughout the Discogs Intelligence Platform (DIP).

Its purpose is to ensure that every implementation—whether produced by a human developer or an AI coding assistant—is consistent with the long-term architecture of the platform.

It complements:

- vision.md
- MarketplaceArchitecture.md
- IntelligenceHistory.md

This document defines **how software should be developed**, not **what features should exist**.

---

# 2. Core Philosophy

The Discogs Intelligence Platform is a long-term software platform rather than a collection of scripts.

Every implementation should prioritise:

- simplicity;
- maintainability;
- determinism;
- explainability;
- incremental evolution.

The objective is to build software that remains understandable years after it is written.

---

# 3. Platform Philosophy

The guiding principle of DIP is:

> Automate the research, not the collecting decision.

The software assists decision making.

It does not make decisions on behalf of users.

No module should produce opaque recommendations.

Every score should be explainable.

---

# 4. Architectural Principles

Every new feature should satisfy the following principles.

## Single Responsibility

Classes should have one clearly defined responsibility.

Modules should solve one problem.

Repositories persist data.

Services coordinate behaviour.

Domain models represent business concepts.

---

## Separation of Concerns

Business logic should never exist inside:

- repositories;
- UI code;
- database implementations.

Presentation should never influence domain behaviour.

---

## Composition over Inheritance

Prefer small composable components.

Avoid deep inheritance hierarchies.

---

## Immutable Domain Models

Prefer frozen dataclasses wherever practical.

Historical data should always be immutable.

---

## Deterministic Behaviour

The same inputs should produce identical outputs.

Avoid hidden state.

Avoid global mutable variables.

Avoid non-deterministic ordering.

---

## Explicit Dependencies

Pass dependencies explicitly.

Avoid service locators.

Avoid hidden singleton behaviour.

---

# 5. Repository Rules

Repositories own persistence.

Repositories do not:

- calculate intelligence;
- calculate scores;
- create UI models;
- perform comparisons.

Repositories simply store and retrieve information.

---

# 6. Service Rules

Application services coordinate workflows.

They may:

- execute engines;
- orchestrate repositories;
- coordinate multiple modules.

They should contain minimal business logic.

---

# 7. Domain Rules

Business rules belong in domain objects or domain services.

They should remain independent of:

- SQLite;
- Tkinter;
- APIs;
- dashboards.

---

# 8. User Interface Rules

Dashboard code should display information.

Explorer code should display information.

UI components should never calculate business logic.

---

# 9. Intelligence Modules

Each Intelligence module should:

- accept an IntelligenceContext;
- return an IntelligenceResult;
- remain deterministic;
- avoid persistence;
- avoid UI concerns.

---

# 10. Testing Philosophy

Every feature should include tests.

Tests should verify behaviour rather than implementation.

Prefer deterministic unit tests.

Avoid unnecessary mocking.

---

# 11. Implementation Strategy

Large features should be implemented incrementally.

Typical order:

1. Models
2. Tests
3. Serialization
4. Repository
5. Services
6. Integration
7. UI

Never implement everything in one change.

---

# 12. Commit Strategy

Prefer many small commits.

Good:

feat: add intelligence history models

Better than:

feat: implement intelligence history

Each commit should compile and pass tests.

---

# 13. Documentation

Every architectural decision should be documented.

Major features should include:

- purpose;
- architecture;
- constraints;
- future extensions.

Documentation should be written before implementation wherever practical.

---

# 14. AI Coding Rules

AI-generated code should:

- follow repository conventions;
- minimise complexity;
- avoid speculative abstractions;
- preserve architecture;
- include tests;
- avoid unrelated refactoring.

AI should not "improve" unrelated code.

---

# 15. Code Review Checklist

Before committing, verify:

✓ Architecture followed

✓ Tests pass

✓ No duplicated logic

✓ No UI coupling

✓ No persistence leakage

✓ Public APIs documented

✓ Type hints included

✓ Names are descriptive

✓ Files remain focused

---

# 16. Future-Proofing

Design for extension.

Do not design for every hypothetical requirement.

Avoid premature abstraction.

Prefer evolving simple code over inventing complex frameworks.

---

# 17. Project Values

The platform should remain:

- deterministic;
- transparent;
- modular;
- testable;
- maintainable;
- explainable;
- enjoyable to develop.

Long-term maintainability always takes precedence over short-term convenience.

# 18. Architectural Decision Record (ADR)
significant architectural decisions should be documented before implementation
---

# Summary

This playbook defines the engineering standards of the Discogs Intelligence Platform.

Whenever uncertainty exists, choose the solution that is:

- simpler;
- clearer;
- more deterministic;
- easier to test;
- easier to explain.

These principles should guide every implementation regardless of whether it is written by a human developer or an AI coding assistant.