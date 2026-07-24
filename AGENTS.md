# AGENTS.md

## Discogs Intelligence Platform

This repository is the Discogs Intelligence Platform (DIP), a long-term intelligence and decision-support platform.

The project follows an architecture-first development approach.

Before changing code, inspect the current branch and read the relevant architecture and development documentation.

---

## Required Reading

Always read:

- `docs/vision.md`
- `docs/Development/AI_Development_Playbook.md`

When working on Intelligence History, historical execution, querying, or comparison, also read:

- `docs/IntelligenceHistory.md`
- `docs/PersistenceArchitecture.md`

When working on Marketplace Intelligence, also read:

- `docs/MarketplaceArchitecture.md`

When working in an area with additional local documentation, read that documentation before implementation.

---

## Platform Principle

The core product principle is:

> Automate the research, not the decision.

DIP is a decision-support platform.

It must not become an automated trading, purchasing, or selling system.

The platform should explain evidence, scores, changes, and uncertainty clearly so that users can make their own decisions.

---

## Architecture Principles

Preserve the existing architectural boundaries.

Conceptually:

```text
Domain Models
      │
      ▼
Domain Services / Engines
      │
      ▼
Application Orchestration
      │
      ▼
Repository Contracts
      │
      ▼
Persistence Adapters
      │
      ▼
SQLite
Presentation layers consume application-facing models and services.

They should not contain business logic, comparison logic, SQL, or persistence orchestration.

---

## Domain Layer

Domain code should:

- remain independent of SQLite and UI frameworks;
- use typed models;
- prefer frozen dataclasses;
- validate stable domain invariants;
- use immutable nested collections where practical;
- preserve deterministic behaviour;
- expose repository protocols in domain terms where required.

Domain code must not import:

- `sqlite3`;
- concrete persistence adapters;
- migrations;
- UI modules.

---

## Application Layer

The application layer coordinates use cases.

Application services may:

- execute engines;
- coordinate repositories;
- assemble application-facing models;
- enforce use-case lifecycle rules;
- coordinate history recording and querying;
- invoke comparison services.

Application services should depend on protocols and abstractions.

They should not instantiate concrete SQLite repositories.

---

## Intelligence Modules

Intelligence modules calculate intelligence.

They should:

- consume an established intelligence context;
- return typed deterministic results;
- expose stable canonical module IDs;
- expose explicit module versions;
- avoid persistence side effects;
- avoid UI concerns;
- avoid querying SQLite directly.

Do not hide important calculations inside presentation code.

Do not introduce one opaque overall score where independent dimensions are more informative.

---

## Intelligence History

Intelligence History stores immutable observations of completed intelligence executions.

Required behaviour:

- one run per completed orchestrated execution;
- one record per completed module result;
- no partial execution persistence;
- deterministic record ordering;
- explicit engine and module versions;
- optional collection snapshot linkage;
- append-only repository APIs;
- strict reconstruction and validation;
- storage-independent domain models.

Unsaved history models must use `None` for database-allocated identifiers.

Do not silently remap objects that claim existing persistent IDs.

---

## Comparison Engine

The Comparison Engine compares previously calculated historical intelligence.

It must not recalculate intelligence.

The architecture is:

    Historical Execution A
              │
              │
    Historical Execution B
              ▼
      Comparison Engine
              │
              ▼
      Comparison Registry
              │
      ┌───────┼────────┐
      ▼       ▼        ▼
 Collection  Hidden   Future
  Health      Gems   Comparers

The engine should:

- remain deterministic;
- remain storage-independent;
- compare complete historical executions;
- align records using canonical module IDs;
- detect added and removed modules;
- use a registry of module comparers;
- keep module-specific comparison logic out of the central engine;
- return immutable structured comparison models.

Generic comparison may compare values without interpretation.

Specialised comparers may later add domain-specific deltas and explanations.

Do not place Dashboard wording or visual formatting in the comparison domain.
## Repository Design

Repository protocols should be:

- storage-independent;
- domain-oriented;
- narrow;
- explicit about ordering and absence semantics.

Repository implementations should:

- reconstruct domain models rather than return raw rows;
- detect malformed stored data;
- preserve deterministic ordering;
- avoid business logic;
- avoid speculative query methods;
- propagate meaningful failures.

Singular absence should generally return `None`.

Plural absence should generally return an empty immutable collection.

Follow existing project conventions where they differ.

---

## Serialization

Use the approved deterministic serialization boundary.

Do not create a generic arbitrary-object serializer.

Persisted complex types must be explicitly approved through registries or allow-lists.

Serialization should preserve:

- tuple semantics;
- enum types;
- dates;
- datetimes;
- finite decimals;
- timedeltas;
- approved domain dataclasses.

Reject:

- unknown tagged values;
- unknown types;
- NaN;
- infinity;
- malformed payloads;
- duplicate JSON keys where relevant.

Do not duplicate serialization logic inside repositories.

---

## Datetimes and Ordering

Preserve exact datetime semantics through serialization.

Where normalized ordering values are required:

- timezone-aware values should be normalized consistently;
- naive datetimes may be treated as UTC for ordering only when documented;
- the original naive value must remain naive when reconstructed.

Every ordered query must define a complete deterministic order.

Timestamp-only ordering is insufficient.

Use stable secondary keys such as persistent IDs.

---

## Migrations

Fresh databases are created from the current schema.

Existing databases are upgraded through ordered migrations.

Both paths must produce equivalent schemas.

Migration requirements:

- deterministic;
- atomic;
- versioned;
- recorded only after success;
- rollback schema, data, and version recording on failure;
- use savepoints when nested inside an existing transaction.

Migration tests must begin from a genuine previous-version schema.

Do not test an upgrade by applying the latest schema first.

Maintain schema and migration parity tests.

---

## UI and Presentation

Dashboard and Explorer code should remain thin.

UI code may:

- request application models;
- select presentation components;
- format values;
- render states and errors.

UI code must not:

- execute SQL;
- calculate intelligence;
- compare historical runs;
- generate domain conclusions;
- control transaction boundaries.

Prefer explicit view models over leaking domain or persistence details into UI components.

---

## Determinism

DIP must produce deterministic results from identical inputs and versions.

Avoid depending on:

- unordered sets;
- incidental dictionary ordering unless explicitly guaranteed by the design;
- database row order without `ORDER BY`;
- runtime subclass discovery;
- unstable display labels as identifiers;
- current time without an injectable clock where tests require control.

Use canonical IDs and explicit versions.

---

## Validation and Errors

Validate inputs at public boundaries.

Reject booleans where Python would otherwise accept them as integers.

Use clear `TypeError` or `ValueError` behaviour consistent with existing code.

Do not silently repair corrupted persistence state.

Do not swallow failures.

Preserve useful causes when translating exceptions.

Avoid broad wrapping that hides the original error.

---

## Testing

Every change should include focused tests.

Prefer:

- unit tests with fakes for application services;
- real SQLite integration tests for repositories and migrations;
- deterministic clocks and fixtures;
- explicit failure-path tests;
- immutability tests;
- ordering tests;
- corruption tests;
- transaction and rollback tests.

When persistence is involved, consider:

- empty state;
- successful writes;
- multiple executions;
- equal timestamps;
- active outer transactions;
- savepoint rollback;
- foreign keys;
- serialization failure before mutation;
- malformed storage;
- fresh-schema and migration parity.

Do not reduce existing coverage to make new changes pass.

---

## Scope Discipline

Implement only the requested slice.

Do not add speculative abstractions or unrelated features.

Unless explicitly requested, do not add:

- UI changes;
- caching;
- background jobs;
- scheduling;
- comparison persistence;
- Marketplace features;
- broad refactors;
- new frameworks;
- premature performance optimisation.

Prefer the smallest architecture-consistent change.

If existing project conventions conflict with a prompt, follow the established architecture and explain the decision.

---

## Documentation

Update architecture documentation when a change establishes or alters a lasting rule.

Do not duplicate large sections across documents.

Use documentation to record:

- boundaries;
- lifecycle;
- failure behaviour;
- ordering;
- invariants;
- extension points;
- deliberate trade-offs.

Do not document speculative features as if they already exist.

---

## Before Making Changes

Before implementation:

1. Inspect the current branch.
2. Inspect the working tree.
3. Read the relevant documentation.
4. Review nearby code and tests.
5. Identify existing conventions.
6. Confirm the requested scope.
7. Avoid changing unrelated files.

Do not assume a planned file path if the repository uses a different established layout.

---

## Before Completing Work

Always:

1. run the full test suite;
2. run project compilation or type checks;
3. run `git diff --check`;
4. inspect the final diff;
5. confirm no unrelated files changed;
6. confirm architectural boundaries remain intact;
7. report assumptions and trade-offs;
8. report any remaining concerns.

Do not commit unless explicitly instructed.

---

## Completion Report

When completing implementation work, report:

1. files created;
2. files modified;
3. architecture and design decisions;
4. lifecycle or transaction behaviour;
5. ordering and validation rules;
6. tests run and results;
7. documentation changes;
8. remaining assumptions or concerns;
9. whether the implementation should be committed unchanged.

---

## Commit Discipline

Commits should be:

- focused;
- small enough to review;
- named for the capability delivered;
- free from unrelated formatting or cleanup changes.

Do not combine unrelated architecture, feature, UI, and maintenance work unless they are inseparable.

Do not create a commit unless the user explicitly asks for one.

---

## Review Standard

The goal is not merely passing tests.

A change should also be:

- architecturally consistent;
- deterministic;
- understandable;
- maintainable;
- explicit about failure behaviour;
- suitable for future extension without unnecessary complexity.

The preferred workflow is:

    Architecture
        ↓
    Implementation
        ↓
    Self-review
        ↓
    Architectural review
        ↓
    Focused refinement
        ↓
    Validation
        ↓
    Commit