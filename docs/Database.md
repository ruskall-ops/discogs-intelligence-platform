# Database Design

> **The database is the historical memory of the Discogs Intelligence
> Platform.**

## Purpose

DIP uses SQLite for implemented collection, legacy Marketplace, Intelligence
History, and aggregate Marketplace History persistence. This document is a
schema overview. Transaction, locking, reconstruction, and migration rules are
defined by [Persistence Architecture](PersistenceArchitecture.md).

Projects are the deliberate exception: version 0.3.0 uses an in-memory Project
repository, so Projects are not stored in SQLite.

## Implemented schema

The current schema in `src/dip/persistence/sqlite/schema.sql` contains:

| Table | Responsibility |
|---|---|
| `schema_migrations` | Applied schema version records |
| `releases` | Canonical imported Discogs release metadata |
| `collection_ownership` | Quantity and ownership-specific collection facts |
| `analysis_runs` | Legacy collection/Marketplace refresh lifecycle |
| `market_snapshots` | Legacy per-release Marketplace observations |
| `scores` | Current legacy collection-review scores |
| `decisions` | User-owned decision, notes, miss rating, and protection state |
| `app_settings` | Key/value application settings |
| `intelligence_runs` | Immutable Intelligence History run metadata |
| `intelligence_results` | Immutable, versioned module result records |
| `marketplace_snapshots` | Canonically serialized aggregate Marketplace snapshots |

`market_snapshots` and `marketplace_snapshots` are intentionally different
contracts. The former supports the original per-release refresh workflow; the
latter stores the exact aggregate Marketplace model used by Marketplace
History.

## Ownership model

`releases` identifies a Discogs release. `collection_ownership` stores one row
per release with a non-negative quantity and ownership facts. Multiple owned
copies are represented by quantity rather than duplicated release rows.

Collection import updates current release and ownership facts. These current
facts are distinct from append-only historical observations.

## Historical storage

### Legacy collection and market history

`analysis_runs` records refresh status and counts. `market_snapshots` stores
per-release observations linked to releases and optionally to an analysis run.
Queries use explicit ordering.

### Intelligence History

`intelligence_runs` and `intelligence_results` store one complete run and one
record per module result. The repository saves a completed execution
atomically, preserves engine and module versions, and reconstructs typed values
through the approved deterministic serializer. Stored corruption is rejected,
not silently repaired.

### Marketplace History

`marketplace_snapshots` stores stable snapshot metadata plus the exact canonical
JSON payload. Capture times have a normalized ordering representation while
the original datetime semantics remain in the payload. Newest-first ordering is
completed by `snapshot_id` as a stable tie-break.

## User-owned state

`decisions` stores mutable user choices separately from Marketplace evidence
and intelligence. A personal decision or note must not modify an objective
observation or calculated historical result.

Marketplace Workspace Research Status is currently presentation state and is
not persisted.

## Connection and transaction boundary

The shared `Database` boundary owns the SQLite connection and lock. Repository
writes participate in its transaction policy. Nested repository operations use
savepoints so a failure rolls back the nested unit without corrupting an active
outer transaction.

Fresh databases are built from the current schema. Existing databases advance
through ordered, atomic migrations. Both paths must remain schema-equivalent.

## Integrity rules

- foreign keys are enabled;
- historical repository writes are atomic;
- ordered queries define deterministic secondary keys;
- serialized domain values use explicit allow-lists;
- malformed or inconsistent persisted history raises an error;
- API tokens and personal databases must not be committed.

## Extension rule

New persistence belongs behind a narrow domain-oriented Repository. Workspaces,
renderers, intelligence modules, and provider adapters must not issue SQL.
Project persistence should be added as a future `ProjectRepository` adapter,
not embedded in Project Workspace or Project Management.
