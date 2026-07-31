# Database Design

> **The database is the historical memory of the Discogs Intelligence
> Platform.**

## Purpose

DIP uses SQLite for implemented collection, legacy Marketplace, Intelligence
History, and aggregate Marketplace History persistence. This document is a
schema overview. Transaction, locking, reconstruction, and migration rules are
defined by [Persistence Architecture](PersistenceArchitecture.md).

Projects use the same SQLite boundary through a dedicated repository adapter.

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
| `projects` | Normalized immutable Project application fields and deterministic order |
| `project_state` | Singleton active-project identity |
| `weekend_review_queue` | Explicit user-owned review items with frozen source evidence |
| `desktop_session` | One optional versioned primary-desktop preference snapshot |

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

`intelligence_runs.marketplace_snapshot_id` is nullable for older and
standalone executions. Non-null values reference `marketplace_snapshots` with
restricted update/delete actions and are unique through a partial index.
Identical repeated saves replay the existing execution; different immutable
content for the same provenance raises a conflict.

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

The Weekend Review Queue is durable user-owned workflow state. It is populated
only by an explicit Add from a calculated Hot-now or Hidden Gem observation.
It freezes source evidence and provenance independently of later calculation
and keeps Collection Decisions in their existing table.

## Project persistence

`projects` stores `project_id`, `name`, `description`, nullable positive
`last_opened_order`, and a unique positive `insertion_order`. Repository reads
reconstruct `ManagedProject` values and list them by insertion order.

`project_state` contains exactly one row with `singleton_id = 1`. Its nullable
`active_project_id` references `projects.project_id` with restricted deletion.
Opening a Project updates active identity and last-opened order atomically.

Migration version 4 creates both tables and the singleton state row. Fresh and
migrated schemas are equivalent. First desktop startup creates
`Current Collection` only when absent and makes it active only when no active
Project exists.

Migration version 5 adds Intelligence History Marketplace provenance and its
partial unique index. Existing runs remain `NULL`; unlimited standalone
`NULL`-provenance executions remain valid. Fresh and upgraded schemas are
equivalent.

Migration version 6 creates an empty `weekend_review_queue`, its unique
release membership, restricted release/Intelligence/Marketplace provenance,
timestamp and lifecycle checks, and deterministic status-order index. It does
not backfill calculated observations. Fresh and genuine v5-to-v6 upgraded
schemas are equivalent.

Migration version 7 creates an empty `desktop_session` singleton table. It has
no Project foreign key or additional index and creates no default row. It
stores only normal geometry, primary navigation, filters, source, stable
selection identities, an optional Project compatibility identifier, format
version, and save timestamp. See
[Session Restoration](SessionRestoration.md).

## Connection and transaction boundary

The shared `Database` boundary owns the SQLite connection and lock. Repository
writes participate in its transaction policy. Nested repository operations use
savepoints so a failure rolls back the nested unit without corrupting an active
outer transaction.

Fresh databases are built from the current schema. Existing databases advance
through ordered, atomic migrations. Both paths must remain schema-equivalent.
Existing databases never receive a second application of the current
`schema.sql`. They run pending migrations and then undergo non-mutating exact
schema validation. Missing or altered objects owned by recorded migrations
fail as schema-integrity errors rather than being recreated. A database with
partial application objects and no coherent migration baseline is not treated
as fresh.

Schema version 7 is current and is distinct from application version 0.5.0.
The Version 0.5 release adds no migration 8.

Complete user-initiated backup uses SQLite's backup API and independent
verification without adding a schema table. See
[Backup and Recovery](BackupAndRecovery.md).

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
Project persistence follows this rule through `SQLiteProjectRepository`;
Project Workspace and Project Management remain SQLite-independent.
