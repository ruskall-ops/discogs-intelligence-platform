# Project Workspace

## Purpose

Project Workspace is the presentation root of the Discogs Intelligence
Platform. A Project represents a collector's working environment and provides
an entry point to the existing Dashboard and Portfolio Workspace.

Version 1 establishes presentation and navigation over Project application
state. A Project is not a stored file, import definition, or configuration
object. Its identity, description, open order, and active state are now
persisted through a repository adapter.

## Architecture

```text
Desktop UI and Project Workspace controller
        ↓
ProjectWorkspacePresentationService
        ↓
ProjectManagementService
        ↓
ProjectRepository
        ↓
SQLiteProjectRepository
        ↓
shared SQLite Database boundary
        ↓
SQLite
```

The presentation service maps application models and invokes the deterministic
`ProjectWorkspaceBuilder`; the desktop renderer receives only the resulting
immutable ViewModel.

The composition root constructs `SQLiteProjectRepository`, ensures one
immutable `Current Collection` Project exists, and injects
`ProjectManagementService` into presentation. A new database makes that default
active. Subsequent starts reuse existing Projects and active state without
duplicating or overwriting the default.

Version 0.4 persists Project metadata, not Project ownership of the rest of the
platform data. Collection, Marketplace, intelligence, history, and research
records are not partitioned by Project. The current desktop is consequently a
practical single-collection workflow, and multi-project UI remains deferred.

## Project Management application layer

`ProjectManagementService` owns application workflows for listing, creating,
opening, selecting the active project, updating last-opened state, and
presenting recent projects. It depends only on the storage-independent
`ProjectRepository` protocol.

`InMemoryProjectRepository` remains the deterministic test and alternative
adapter. Normal desktop execution uses `SQLiteProjectRepository`. Both preserve
insertion order and use a monotonically increasing integer for deterministic
last-opened ordering. Recent projects exclude the active Project and Projects
that have never been opened, then use last-opened order descending and Project
identity as a stable tie-break.

The application `ManagedProject` model is immutable and separate from the
presentation-only `Project` model. The presentation service performs the
one-way mapping and assigns active or recent presentation status. Workspace
builders and renderers never receive a repository.

## Responsibilities

The workspace presents:

- the active project;
- recent projects in supplied order;
- a presentation-ready project summary; and
- deterministic quick actions.

Open Project, Create Project, and Refresh Collection are disabled placeholders.
Open Dashboard and Open Portfolio Workspace navigate through existing desktop
methods. No routing framework or controller logic is duplicated.

## Boundaries

Project Workspace performs no file access, repository access, importing,
configuration, SQLite access, networking,
intelligence execution, calculation, or analysis. Models and nested
collections are immutable, and the builder does not sort supplied projects.

The application service orchestrates only the storage-independent
`ProjectRepository`. SQLite mapping, constraints, reconstruction, error
translation, and transactions remain inside the adapter. Opening a Project
atomically updates last-opened and active state.

## Future extensions

Future milestones may introduce file selection, project creation UI, a
Project-scoped collector run pipeline, and broader workspace restoration.
The implemented primary desktop session uses the already-active Project only
as a compatibility guard; it never selects or mutates a Project and does not
make platform data Project-scoped. See
[Session Restoration](SessionRestoration.md). Project persistence alone does
not implement file selection, Project creation UI, data partitioning, or
broader restoration. Those capabilities must remain outside the presentation
builder and desktop renderer and use the existing application and repository
boundaries.
