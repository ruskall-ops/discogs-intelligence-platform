# Project Workspace

## Purpose

Project Workspace is the presentation root of the Discogs Intelligence
Platform. A Project represents a collector's working environment and provides
an entry point to the existing Dashboard and Portfolio Workspace.

Version 1 establishes presentation and navigation only. A Project is not a
stored file, persistence record, import definition, or configuration object.

## Architecture

```text
ProjectManagementService
        ↓
ProjectWorkspacePresentationService
        ↓
ProjectWorkspaceBuilder
        ↓
immutable Project Workspace ViewModel
        ↓
DesktopProjectWorkspaceRenderer
```

The composition root constructs a deterministic `InMemoryProjectRepository`,
seeds one immutable `Current Collection` project, and injects a
`ProjectManagementService` into presentation. No project is discovered, loaded
from external storage, saved, or restored.

## Project Management application layer

`ProjectManagementService` owns application workflows for listing, creating,
opening, selecting the active project, updating last-opened state, and
presenting recent projects. It depends only on the storage-independent
`ProjectRepository` protocol.

The first repository adapter is `InMemoryProjectRepository`. It preserves
insertion order for project listing and uses a monotonically increasing integer
for deterministic last-opened ordering. Recent projects exclude the active
project and projects that have never been opened, then use last-opened order
descending and project identity as a stable tie-break.

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
configuration, persistence, SQLite access, networking,
intelligence execution, calculation, or analysis. Models and nested
collections are immutable, and the builder does not sort supplied projects.

The application service may orchestrate its repository, but contains no
storage implementation. The in-memory adapter is process-local and provides no
session restoration.

## Future extensions

Future milestones may introduce persistence adapters, file selection, project
creation UI, and session restoration. Those capabilities must remain outside
the presentation builder and desktop renderer and must be supplied through the
existing application and repository boundaries.
