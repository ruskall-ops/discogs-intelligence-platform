# Persistence Architecture

## Purpose

This document defines the persistence architecture for the Discogs Intelligence Platform (DIP).

Its purpose is to establish one consistent approach to:

- SQLite connection ownership;
- locking;
- transaction boundaries;
- nested transaction behaviour;
- repository responsibilities;
- schema creation;
- migrations;
- serialization;
- reconstruction of domain models;
- testing;
- failure handling.

It complements:

- `docs/vision.md`
- `docs/Development/AI_Development_Playbook.md`
- `docs/IntelligenceHistory.md`
- `docs/MarketplaceArchitecture.md`

This document describes how persistence infrastructure should behave across the platform.

It does not define business rules for individual domains.

---

# Core Principle

Persistence stores and retrieves domain state.

Persistence must not calculate intelligence, interpret results, or influence presentation.

Conceptually:

```text
Domain Models
      │
      ▼
Repository Contract
      │
      ▼
Persistence Adapter
      │
      ▼
Database Boundary
      │
      ▼
SQLite
```

Each layer has a distinct responsibility.

---

# Design Goals

The persistence architecture should:

- keep domain code independent of SQLite;
- provide deterministic behaviour;
- provide explicit transaction ownership;
- coordinate access to shared SQLite connections;
- support nested repository operations safely;
- preserve immutable historical data;
- keep migrations atomic;
- prevent schema drift;
- support comprehensive automated testing;
- remain simple enough for a desktop application;
- allow future replacement of SQLite adapters if required.

---

# Architectural Layers

## Domain Layer

The domain layer contains:

- immutable models;
- business rules;
- domain validation;
- repository protocols.

The domain layer must not import:

- `sqlite3`;
- migration modules;
- schema files;
- UI code.

## Repository Contracts

Repository contracts define persistence capabilities in domain terms.

Examples include:

- save an intelligence execution;
- retrieve the latest run;
- retrieve module history;
- load a collection snapshot.

Repository contracts should not expose:

- SQL;
- table names;
- cursors;
- raw database rows;
- connection objects.

## Persistence Adapters

Persistence adapters implement repository contracts for a specific storage technology.

For SQLite, adapters belong under:

```text
src/dip/persistence/sqlite/
```

Adapters may know about:

- SQL;
- schema details;
- row factories;
- SQLite constraints;
- indexes;
- transaction scopes.

Adapters must not contain business logic.

## Database Boundary

The project-level `Database` abstraction owns the shared SQLite boundary.

It is responsible for:

- connection lifecycle;
- connection configuration;
- shared locking;
- transaction coordination;
- nested transaction handling;
- migration execution;
- access to configured connections.

Repositories should use this boundary rather than independently managing the same connection.

---

# Connection Ownership

A SQLite connection has one clear owner.

For the desktop application, the owner is the project-level `Database` abstraction.

Repositories should not:

- close the shared connection;
- replace its row factory;
- change global connection settings unexpectedly;
- create independent locks around the same connection;
- commit or roll back outside the approved transaction boundary.

A repository may use a dedicated connection only when the architecture explicitly chooses that model.

---

# Connection Configuration

Connections should be configured consistently.

Expected configuration may include:

- `sqlite3.Row` row factory;
- foreign keys enabled;
- thread access consistent with the application design;
- deterministic text handling;
- explicit transaction behaviour.

Repositories may assume these settings only when they receive the connection through the project Database boundary.

Raw externally supplied connections should either be rejected or validated.

---

# Shared Locking

All access to a shared connection must coordinate through one shared lock.

Creating one lock per repository does not protect the connection because different locks do not coordinate.

The Database abstraction should expose controlled access such as:

```python
with database.locked_connection() as connection:
    ...
```

Reads and writes using the same shared connection should use the same synchronization mechanism.

The lock should be re-entrant where nested project operations require it.

---

# Transaction Ownership

Transaction ownership must always be explicit.

A repository operation may run in one of two contexts.

## Repository-Owned Transaction

When no transaction is active:

```text
Repository call

↓

Begin transaction

↓

Perform complete operation

↓

Commit or rollback
```

The repository operation owns the transaction through the Database boundary.

## Caller-Owned Transaction

When a caller already owns a transaction:

```text
Caller transaction

↓

Repository savepoint

↓

Repository operation

↓

Release savepoint or rollback to savepoint

↓

Caller retains final commit or rollback control
```

The repository must not commit or roll back the caller's entire transaction.

---

# Nested Transactions

SQLite does not provide fully independent nested transactions.

Nested behaviour should therefore use savepoints.

Savepoint requirements:

- unique names;
- deterministic lifecycle;
- release on success;
- rollback to savepoint on failure;
- preserve earlier caller work;
- leave outer transaction ownership unchanged.

The Database abstraction should own savepoint creation rather than each repository inventing its own implementation.

---

# Returned Identifiers Inside Transactions

A repository may return a generated identifier before an outer transaction commits.

Example:

```text
save_execution() returns run_id=42

↓

Caller later rolls back outer transaction

↓

run_id=42 is no longer persistent
```

This is normal transactional behaviour.

Callers must not assume persistence is final until the owning transaction commits.

---

# Transaction Scope

One domain operation should normally map to one atomic persistence operation.

For Intelligence History:

```text
Insert run

↓

Insert every associated result

↓

Commit
```

Either the complete execution is persisted or none of it is.

Partial historical executions must not remain.

---

# Pre-Transaction Work

Validation and serialization should occur before database mutation where practical.

Benefits include:

- failure before opening a transaction;
- shorter transaction duration;
- simpler rollback behaviour;
- fewer partial-operation risks.

Database-dependent validation may still occur within the transaction.

---

# Repository Responsibilities

Repositories own:

- persistence;
- reconstruction;
- query ordering;
- transaction participation;
- storage errors;
- storage-specific constraints.

Repositories do not own:

- intelligence calculation;
- score calculation;
- comparison logic;
- Dashboard view models;
- Explorer presentation;
- user-facing recommendations.

---

# Append-Only Historical Data

Historical repositories should expose append-only APIs.

They should not provide update or overwrite methods for historical records.

For the current desktop architecture, append-only behaviour may be enforced through repository APIs rather than database triggers.

Database-level protection may be introduced later if tamper resistance or external database access becomes a requirement.

---

# Unsaved and Persisted Models

Unsaved models should represent their state explicitly.

For example:

```python
run_id = None
record_id = None
```

A repository allocates database identifiers.

Input objects must not claim existing persistent identifiers unless the repository operation explicitly supports that case.

Repositories should reject ambiguous association states instead of silently remapping them.

---

# Serialization Boundary

Complex domain values should use the domain's approved serialization API.

Repositories must not duplicate serialization logic.

For Intelligence History, the SQLite adapter must use:

- `serialize_intelligence_value`;
- `deserialize_intelligence_value`;
- `dumps_intelligence_value`;
- `loads_intelligence_value`.

This preserves:

- deterministic output;
- strict validation;
- tuple semantics;
- enum semantics;
- date and datetime semantics;
- approved model boundaries.

---

# Sortable and Exact Representations

Sometimes persistence needs both:

- an exact serialized representation;
- a normalized query representation.

For example, Intelligence History stores:

- the exact serialized datetime;
- a normalized sortable execution timestamp.

This is acceptable when each field has a distinct purpose.

The exact representation preserves domain semantics.

The normalized representation supports efficient deterministic ordering.

---

# Datetime Policy

Timezone-aware datetimes should be normalized consistently for ordering.

Naive datetimes remain naive in their exact serialized form.

Where ordering requires a normalized value, naive datetimes are treated as UTC unless a domain-specific policy replaces this rule.

This interpretation must be documented because it is an ordering convention, not a change to the original datetime value.

---

# Deterministic Ordering

Every query that returns ordered results must define a complete order.

Timestamp ordering alone is insufficient because multiple records may share the same timestamp.

A deterministic secondary key should be used.

Typical pattern:

```sql
ORDER BY executed_at DESC, id DESC
```

Chronological results should similarly use:

```sql
ORDER BY executed_at ASC, id ASC
```

---

# Schema Design

Schemas should reflect domain invariants that are stable and storage-appropriate.

Examples include:

- `NOT NULL`;
- foreign keys;
- uniqueness;
- non-negative count checks;
- append-only associations.

Business rules that change frequently should generally remain outside the schema.

---

# Foreign Keys

Foreign keys should be enabled on every configured SQLite connection.

They should be used where ownership is clear.

For example:

```text
intelligence_results.run_id
        ↓
intelligence_runs.id
```

Optional loose references should not be forced into foreign keys when the referenced domain table does not yet exist or intentional decoupling is required.

---

# Indexing

Indexes should support demonstrated query patterns.

They should not be added speculatively.

Before adding an index, consider:

- filter columns;
- join columns;
- ordering columns;
- existing indexes created by unique constraints;
- write overhead;
- query-plan evidence.

Redundant indexes should be removed.

---

# Fresh Schema and Migrations

The project supports two database paths.

## Fresh Database

A new database is created from the current `schema.sql`.

## Existing Database

An existing database is upgraded through ordered migrations.

Both paths must produce equivalent current schemas.

---

# Migration Rules

Each migration should:

- have a unique version;
- run once;
- be deterministic;
- remain atomic;
- avoid unrelated changes;
- preserve existing data where practical;
- record its version only after successful completion.

Migration failures must roll back:

- schema changes;
- data changes;
- migration-version recording.

---

# Migration Savepoints

Migration execution should use the same project-level transaction rules.

When a migration runs inside an existing transaction, it should use a savepoint.

Failed DDL must not survive a nominal rollback.

---

# `IF NOT EXISTS`

`IF NOT EXISTS` may improve idempotence, but it can hide incompatible pre-existing schemas.

Where it is used, tests should verify the resulting:

- columns;
- nullability;
- checks;
- foreign keys;
- unique constraints;
- indexes.

Successful execution alone is not sufficient proof of a correct migration.

---

# Schema and Migration Parity

Schema definitions duplicated between `schema.sql` and migrations create drift risk.

Automated tests should compare the fresh-schema result with the migrated result.

Parity tests should verify at least:

- table names;
- columns;
- types;
- nullability;
- default values;
- checks;
- foreign keys;
- unique constraints;
- named indexes.

---

# Migration Testing

Migration tests should start from a genuine previous-version schema.

They should not initialize the latest schema before running the migration under test.

A version 1 to version 2 test should:

1. install the version 1 schema;
2. record migration version 1;
3. execute the migration runner;
4. verify version 2;
5. inspect the resulting schema;
6. compare it with a fresh current database.

---

# Repository Testing

Every repository implementation should test:

- empty database behaviour;
- successful writes;
- multiple records;
- deterministic ordering;
- optional fields;
- malformed stored data;
- serialization failure;
- constraint failure;
- rollback;
- active outer transactions;
- savepoint behaviour;
- foreign-key behaviour;
- closed connection behaviour where relevant.

---

# Concurrency Testing

Where the shared connection may be used across threads, tests should confirm:

- one shared lock coordinates access;
- repository operations block appropriately;
- no independent ineffective locks are introduced;
- transaction ownership remains correct.

Concurrency tests should remain focused and deterministic.

---

# Error Handling

Persistence errors should preserve useful context without exposing raw implementation details unnecessarily.

The architecture should distinguish:

- serialization errors;
- deserialization errors;
- domain validation errors;
- constraint failures;
- migration failures;
- connection failures.

Errors should not be silently ignored.

---

# Corrupted Stored Data

Stored data must be treated as untrusted at the reconstruction boundary.

Deserialization should:

- validate tagged values;
- validate model field types;
- reject malformed values;
- produce clear field paths where possible.

Repositories should not construct invalid domain objects from corrupted rows.

---

# Row Reconstruction

Adapters should reconstruct domain models explicitly.

They should not return raw rows to callers.

Reconstruction should preserve:

- immutable models;
- exact versions;
- optional values;
- enum types;
- dates and datetimes;
- deterministic collection types.

---

# Package Structure

The preferred conceptual structure is:

```text
src/dip/
    <domain>/
        models.py
        repository.py

    persistence/
        sqlite/
            repository.py
            <domain_adapter>.py
            schema.sql
            migrations/
```

Domain protocols remain with the domain.

SQLite implementations remain with SQLite persistence.

---

# Public API Boundaries

The domain package may export:

- models;
- repository protocols;
- domain errors.

The SQLite persistence package may export:

- concrete repository adapters;
- Database infrastructure where appropriate.

Internal transaction helpers, migration internals, and SQL helpers should remain private unless there is a clear reuse case.

---

# Logging

Persistence logging should be useful but restrained.

Appropriate events include:

- migration start and completion;
- migration failure;
- database initialization failure;
- repository operation failure where context is needed.

Sensitive or excessively detailed payloads should not be logged.

---

# Performance

Correctness and clarity take priority over premature optimization.

Performance work should be driven by:

- measured query plans;
- realistic data volumes;
- observed latency;
- actual write frequency.

Optimization must not weaken transaction guarantees or domain validation.

---

# Backup and Recovery

SQLite database files should remain portable and recoverable.

Future backup features should coordinate with active transactions and avoid copying inconsistent database state.

This may use SQLite-supported backup mechanisms rather than raw file copying while the database is active.

Backup implementation is outside the current scope.

---

# Architectural Constraints

The persistence implementation must:

- keep SQLite outside domain code;
- use the shared Database boundary;
- coordinate through one shared lock;
- make transaction ownership explicit;
- use savepoints for nested operations;
- preserve atomic domain operations;
- use parameterized SQL;
- enforce deterministic ordering;
- reuse approved serializers;
- validate reconstructed models;
- keep schema and migrations equivalent;
- avoid unrelated business logic;
- avoid speculative infrastructure.

---

# Review Checklist

Before committing persistence work, verify:

- domain protocols remain SQLite-independent;
- repository adapters use the shared Database boundary;
- no independent lock protects the same shared connection;
- outer transactions are not committed or rolled back unexpectedly;
- nested failures roll back only to their savepoint;
- serialization occurs before mutation where practical;
- all SQL is parameterized;
- ordering has deterministic tie-breaking;
- migrations are genuinely upgrade-tested;
- migration failure is atomic;
- fresh and migrated schemas are equivalent;
- indexes are justified and non-redundant;
- full tests pass;
- `git diff --check` passes.

---

# Future Extensions

The architecture may later support:

- dedicated read connections;
- write queues;
- WAL-specific policies;
- repository factories;
- backup services;
- database health diagnostics;
- migration repair tooling;
- alternative persistence adapters.

These should extend the current boundaries rather than bypass them.

---

# Summary

Persistence in DIP is infrastructure, not intelligence.

The domain defines meaning.

Repositories define storage capabilities.

SQLite adapters translate those capabilities into SQL.

The Database boundary owns the connection, lock, and transaction lifecycle.

Migrations evolve the schema safely.

Tests prove that fresh and upgraded databases behave identically.

The central rule is:

> One shared connection boundary, one coordinated lock, and explicit transaction ownership.

Following this architecture keeps DIP deterministic, reliable, and maintainable as the platform grows.