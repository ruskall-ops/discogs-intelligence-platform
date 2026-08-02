# Database Backup and Recovery

## Purpose

DIP provides an explicit **Back Up Database…** desktop action for personal-use
recovery. A backup is a complete SQLite database, not a CSV export, cloud
synchronization service, or selective copy.

## Creating a backup

Backup is available during normal use and unavailable while Collector Run or
another backup is active. A dirty Weekend Review Queue note must first be
Saved, Discarded, or Cancelled. Cancel and note-save failure stop before the
Save As dialog.

The suggested UTC filename is:

```text
discogs-intelligence-backup-YYYYMMDD-HHMMSSZ.sqlite3
```

The collector chooses an existing destination folder. DIP does not remember a
default folder, schedule backups, retain generations, or delete old files. An
existing file requires explicit replacement confirmation. The selected target
itself must not be a symbolic link. A symbolic link in the chosen parent path
is allowed after resolution because live-database equivalence is checked
against the resolved target.

SQLite's supported backup API creates a consistent temporary database under
the shared database lock. DIP independently checks SQLite integrity, foreign
keys, migration versions, and tables before atomically publishing the selected
file. A failed operation leaves the live database and any previous backup
unchanged. The backup captures durable collection, decision, note, history,
Marketplace, Project, queue, session, and migration state. Unsaved drafts and
calculated screen models are not included.

## Compatibility

Restore a backup with the same DIP version or a newer compatible version that
can migrate its schema. Do not open a newer-schema backup with an older DIP
version. Schema version 7 and application version 0.5.1 are separate version
identities. DIP v0.5.1 is the prepared release candidate. It is implemented and
validated and is awaiting release completion. DIP v0.5.0 remains the latest
completed, tagged public personal-use release.

## Manual recovery

DIP has no Restore button. Recovery is deliberately manual:

1. Close DIP fully.
2. Preserve the current database by renaming or copying it.
3. Copy the selected `.sqlite3` backup to the configured database location.
4. Launch DIP normally.
5. Allow normal validation and ordered migrations to complete.
6. Verify the expected collection, decisions, history, Project, queue, and
   session state.

Rehearse recovery only with disposable copies. Never test recovery against the
only copy of a personal database.
