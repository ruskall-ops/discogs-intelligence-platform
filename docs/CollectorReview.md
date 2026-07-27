# Collector Review

## Purpose

Collector Review turns already-calculated research signals into an explicit,
collector-owned workflow:

```text
Calculated observations
        ↓ inspect evidence
Explicit Add to Weekend Review Queue
        ↓
Note and review status
        ↓
Resolve, reopen, or remove
```

It follows the platform principle: **Automate the research, not the decision.**
Neither an observation nor a queue item is a recommendation to buy or sell.
The implemented v0.5.4 slice remains single-collection and unreleased; the
package/runtime version remains `0.4.0`.

## Architectural boundaries

The immutable observation workspace is assembled by
`WeekendObservationService` from repository and history-query boundaries. It
does not score releases, execute Intelligence, contact providers, or mutate
the queue. During one Dashboard refresh the card and Collection Review
drill-down consume the same workspace instance.

The two observation sources remain independent:

- **Hot now** reads only persisted scores classified `Hot now`;
- **Hidden Gems** reconstructs the latest persisted `hidden_gems` Intelligence
  result.

Queue membership is release-based, so the same release shown in both sections
has one queue state. Observation identity remains `(source, release_id)`.

## Evidence and provenance

Hot-now rows retain their stored score components, explanation, calculation
time, and exact matching legacy snapshot. Provenance resolution follows the
legacy analysis run to its deterministic canonical Collector Run snapshot and,
when present, the matching Intelligence execution. Timestamp equality alone is
not proof. Evidence shown for a score always comes from its origin; newer
Marketplace evidence may mark it stale but is never substituted.

Safe warnings distinguish retained scores, failed source runs, unavailable
provenance, stale scores, and partial Marketplace evidence. Failed, empty, or
unavailable canonical observations cannot substantiate a score.

Hidden Gems preserves the stored candidate order, factors, metrics, evidence,
execution identity, and canonical Marketplace provenance. A completed result
must already be ordered by score descending and release ID ascending. A
legitimately skipped result is an available empty section. Legacy results
without Marketplace provenance remain visible with a warning; invalid
referenced provenance becomes a safe unavailable state.

## Weekend Review Queue

Population is never automatic. Only **Add to Weekend Review Queue** creates a
row. A duplicate active add returns the existing item unchanged; a resolved
duplicate requires explicit Reopen. Collector Run, Dashboard refresh,
observation refresh, and Intelligence execution never mutate queue state.

Each item freezes:

- its source type and observed time;
- a neutral, deterministic source summary;
- its original Intelligence and Marketplace provenance when available;
- its added time, review note, status, and last-updated time.

Hot-now summaries preserve the stored explanation. Hidden Gem summaries
preserve rank, score, and the first stored evidence statement, with a neutral
fallback when evidence is absent. Later calculated changes do not rewrite
either summary.

The lifecycle is:

```text
to_review ↔ reviewing → resolved
     ↑                    │
     └──── explicit Reopen┘
```

Resolve records its time. Reopen preserves identity, `added_at`, note, and
frozen evidence. Identical note/status updates and repeated resolution are
no-ops. Remove is a confirmed hard deletion of the queue item only; release,
history, Marketplace evidence, and Collection Decisions remain untouched.

Writes use normalized UTC microsecond timestamps and optimistic
`updated_at` checks. Every real mutation calls the clock once and advances the
token by one microsecond from the persisted UTC instant when the clock is equal
or earlier, so rapid writes cannot reuse a stale token. Missing items, stale
writes, corrupt data, and persistence failures have distinct safe outcomes.
Repositories participate in the shared database transaction and use savepoints
inside caller-owned transactions.

## Desktop workflow

Collection Review contains:

1. **Observations** — Hot now and Hidden Gems lists with read-only evidence,
   warnings, Add, Reopen, and Open Queue actions.
2. **Weekend Review Queue** — active by default, with resolved/all filters,
   explicit note Save, active status changes, Resolve/Reopen, confirmed Remove,
   and navigation to Collection Decisions.
3. **Collection Decisions** — the existing independent editor and persistence.

Unsaved queue notes require Save, Discard, or Cancel before changing queue
selection, changing Collection Review destination, or closing the application.
Refresh never silently saves or discards the buffer. Queue controls remain
available while Collector Run executes; its Tkinter terminal callback refreshes
calculated Observations only.

## Persistence

Migration 6 adds `weekend_review_queue` and
`idx_weekend_review_queue_status_order`. The table has one row per release,
validated status/source values, ordered aware timestamps, restricted foreign
keys to release and optional source evidence, and source-specific provenance
checks. Migration 6 creates an empty queue and does not derive items from
existing scores or Intelligence History. Fresh-schema and genuine v5-to-v6
upgrade paths are equivalent.

## Deliberate exclusions

This slice adds no Project partitioning, automatic queue
population, recommendations, alerts, scheduling, tags, priority, manual order,
status audit history, listing acquisition, scoring changes, or duplicated
Collection Decision persistence.

The v0.5.5 session boundary may restore the selected Review destination,
source, filter, and exact visible observation or queue identity after fresh
queries. It never persists Review-note drafts or changes the existing
Save/Discard/Cancel lifecycle. See
[Session Restoration](SessionRestoration.md).
