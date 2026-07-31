# Session Restoration

## Purpose

Session Restoration preserves a small set of database-scoped desktop
preferences across graceful application restarts. It improves continuity
without treating calculated presentation models, unsaved drafts, or running
processes as durable state.

Session Restoration was released as part of DIP v0.5.0 on 31 July 2026.

Database backup does not trigger a special session save. It captures the last
successfully stored session row; graceful close remains the session persistence
boundary.

## Architecture

```text
Desktop capture and application
        ↓
SessionRestorationService
        ↓
SessionRepository
        ↓
SQLiteSessionRepository
        ↓
desktop_session
```

The desktop captures typed widget state and applies restored preferences.
`SessionRestorationService` owns the save timestamp and coordinates the
repository. The repository owns reconstruction, canonical timestamps, SQL, and
atomic replacement. Composition constructs and injects these dependencies but
does not load or save a session.

## Restored state

Version 1 restores:

- normal main-window width, height, X, and Y;
- Project, Dashboard, or Collection Review as the top-level destination;
- Observations, Weekend Review Queue, or Collection Decisions as the nested
  Collection Review destination;
- Hot now or Hidden Gems observation source;
- Active, Resolved, or All queue filter;
- Collection Decision Priority and Decision filters;
- an optional exact `ObservationIdentity`;
- an optional queue item ID;
- an optional Collection Decision release ID.

Search text is deliberately not saved. Display labels and notebook indexes are
mapped to stable enum values before persistence.

Selections are applied only after fresh queries. A missing or filtered-out
identity clears selection without changing filters, choosing a substitute,
opening an editor, or mutating domain state.

## Project compatibility

The active Project remains owned by Project Management and Project
persistence. Session state stores its identifier only as a compatibility
guard. Geometry can be restored for every valid session. Navigation, filters,
source, and selections are restored only when the stored identifier equals the
already-active durable Project.

A missing or different Project produces deterministic navigation defaults. It
does not create, activate, open, or modify a Project. Session restoration does
not make collection, Marketplace, intelligence, decision, or review data
Project-scoped.

## Geometry safety

Only the last valid normal geometry is captured. Minimized, maximized, zoomed,
full-screen, and secondary-window state are neither saved nor restored.

Restoration uses Tk's virtual-root bounds. Negative coordinates remain valid
for multi-monitor desktops. Size is bounded by the current virtual desktop
while respecting the application's minimum size. A position with less than
160 horizontal or 64 vertical visible pixels is centered. If reliable screen
bounds are unavailable, only dimensions are restored and the platform chooses
placement.

Corrected geometry is not persisted until a later successful graceful close.

## Startup

After composition and widget construction, the desktop loads the session,
checks Project compatibility, applies geometry and accepted filters, queries
fresh Dashboard, observation, queue, and decision state, restores exact visible
navigation, and then restores exact visible selections.

A restoration guard prevents callbacks from treating startup application as a
user command and is cleared unconditionally after every restoration outcome.
Successful restoration is silent. Absence is a normal first-run state. Load
failure or structural corruption uses deterministic defaults and does not
prevent startup.

Sanitized positioned geometry falls back to dimensions-only placement if the
window manager rejects it. If that is also rejected, the established platform
default remains in use. Unknown display labels or notebook destinations reject
session capture rather than being converted to semantic defaults, and
compatibility errors use fixed value-neutral messages.

## Shutdown

Close is refused while Collector Run is active. The application adds no
cancellation, waiting, resumption, or recovery behavior.

Otherwise the existing Weekend Review note Save, Discard, or Cancel lifecycle
runs before session capture. Cancel or note-save failure keeps the application
open and performs no session write.

Both the main-window close request and the macOS application Quit command enter
this same graceful-close boundary. Application-level Quit must not bypass
session capture.

The session is then atomically replaced. If saving fails, the collector chooses
`Close Without Saving` or `Stay Open`. Previously saved queue notes and
decisions remain independent. Database-close failure leaves the root open and
shows a safe generic error.

## Persistence

Migration 7 adds the empty singleton `desktop_session` table. It creates no
default row, foreign key, additional index, history, checksum, or optimistic
lock. `get()` returns `None` when absent. `save()` uses the shared
savepoint-aware database transaction boundary and single-process
last-write-wins replacement.

Timestamps are aware UTC ISO 8601 values with microseconds. Structural
corruption rejects the complete stored record. Unknown format versions are
incompatible rather than silently reinterpreted. A failed replacement leaves
the previous valid row intact.

## Privacy and exclusions

Session storage never contains:

- Discogs credentials, provider clients, responses, or raw errors;
- database or export paths;
- queue-note or Collection Decision drafts;
- personal notes duplicated from domain storage;
- Dashboard, observation, Portfolio, Marketplace, Explorer, or History models;
- Collector Run worker, progress, callback, or resumable-process state;
- secondary-window presence or geometry;
- minimized, maximized, zoomed, or full-screen state.

Draft recovery, search restoration, Project partitioning, reset UI, generic
preferences, cloud synchronization, and secondary-workspace restoration remain
outside v0.5.5.
