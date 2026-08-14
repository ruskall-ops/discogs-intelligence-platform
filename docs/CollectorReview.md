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
Collector Review was released as part of DIP v0.5.0 on 31 July 2026 and remains
single-collection.

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
Warning codes are mapped to fixed public copy; raw provider messages, paths,
serialized payloads, database details, and personal notes are never rendered.
The warning projection accepts a closed semantic state: evidence limitations
are shown only in the compatible state, while incompatible states suppress
both known and unknown warnings. Unknown compatible warnings collapse to one
fixed generic limitation.
Observation detail keeps calculated facts, Marketplace evidence, limitations,
queue state, and indented technical provenance as distinct labelled sections.

Collection Decisions preserve unavailable numeric facts as an em dash and
preserve real zeroes as `0.00` for prices, `0` for counts, and `0.0` for
scores. The horizontally scrollable table does not truncate long artist or
title values in the underlying row and retains selection only by release ID.

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

Collection Decisions retains every existing column and adds horizontal
overflow. Artist, title, classifications, priority, and decision remain
left-aligned; price, wants, supply, and score facts are right-aligned. Missing
facts use an em dash and remain distinct from genuine zero. The supplied lowest-
price numeric value is formatted to two decimal places in the fixed `Lowest £`
column: missing price evidence appears as an em dash and genuine zero as
`0.00`. The repository currency field is not separately projected in this table.
Filtering and reload preserve the exact selected release while it remains
visible and clear selection without choosing a substitute when it does not.
Decision and Priority filters use one immutable typed vocabulary. Canonical
choices keep their established order. Any other exact values retained by an
older or externally populated database remain displayed and exported unchanged
and appear afterward as deterministic, read-only `Retained: …` filter choices.
The rendered label is never parsed as query identity: canonical, retained, and
the unfiltered **All** choice remain distinct even when retained data is itself
named `All` or differs only by case. Filtering continues to use exact stored
equality and performs no normalization, inference, provider request, write, or
score calculation.
Each table reload performs one bounded-purpose distinct-value discovery query
followed by the existing bounded row query. Switching tabs alone does not run
either query; the established load/reload boundary does.

The Collection Decision editor continues to offer exactly **Review**, **Keep**,
**List for sale**, **Maybe**, and **Ignore** for new writes. Persistence rejects
unknown, blank, untrimmed, boolean, and non-string decision inputs before a
transaction begins. Opening or cancelling an editor for a retained value does
not rewrite it; saving requires an explicit canonical choice. There is no data
migration or automatic normalization.

Canonical Decision and Priority filters participate in session restoration.
Retained compatibility selections are intentionally session-local. When one is
selected at graceful close, session v1 stores the existing canonical **All**
token; after restart the table restores **All** and rediscovers every retained
value as an individually selectable choice. This fallback neither normalizes
stored rows nor substitutes or infers a canonical meaning.

Selected Observation detail is grouped from typed fields into Calculated
observation, Marketplace evidence, Evidence limitations / warnings, Weekend
Review Queue state, and subordinate Technical provenance sections when those
values exist. Current catalogue labels are identified as current and are not
represented as historical evidence. Workflow actions are visually separate,
and disabled controls have nearby textual explanations. Local Tab, Shift-Tab,
Return, and Space handling preserves mouse and keyboard use at `800×560`; it
does not change queue lifecycle, unsaved-note, evidence, provider, or write
boundaries.

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
