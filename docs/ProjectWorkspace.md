# Project Workspace

## Purpose

Project Workspace is the presentation root of the Discogs Intelligence
Platform. A Project represents a collector's working environment and provides
an entry point to the existing Dashboard and Portfolio Workspace.

Version 1 establishes presentation and navigation only. A Project is not a
stored file, persistence record, import definition, or configuration object.

## Architecture

```text
Project Services (future)
        ↓
ProjectWorkspacePresentationService
        ↓
ProjectWorkspaceBuilder
        ↓
immutable Project Workspace ViewModel
        ↓
DesktopProjectWorkspaceRenderer
```

The composition root currently supplies one immutable `Current Collection`
project. No project is discovered, loaded, saved, or restored.

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

Project Workspace performs no file access, project retrieval, importing,
configuration, persistence, SQLite access, repository access, networking,
intelligence execution, calculation, or analysis. Models and nested
collections are immutable, and the builder does not sort supplied projects.

## Future extensions

Future milestones may introduce Project Services, persistence adapters,
project creation, file selection, recent-project retrieval, and session
restoration. Those capabilities must remain outside the presentation builder
and desktop renderer and must be supplied through explicit application
boundaries.
