# PROJECT_BOOTSTRAP.md

> **This document is the primary onboarding guide for anyone contributing to the Discogs Intelligence Platform (DIP).**
>
> It explains the vision, engineering philosophy, architecture, current state of development and working practices so development can continue consistently across future sessions.

---

# What is DIP?

The Discogs Intelligence Platform (DIP) is a long-term software project designed to become an evidence-based decision support platform for vinyl collectors.

Its purpose is **not** to tell collectors what to buy or sell.

Instead it automates the research required to make informed collecting decisions.

Core philosophy:

> **Automate the research, not the collecting decision.**

---

# Current Development Stage

Current Milestone:

**Version 0.1 – Core Platform**

The current objective is to build a robust engineering foundation before adding advanced intelligence features.

The project deliberately prioritises:

- Architecture
- Data integrity
- Historical tracking
- Maintainability

over adding visible features quickly.

---

# Current Project Status

Completed GitHub Issues

- ✅ Database Foundation
- ✅ Import Engine
- ✅ Modular Project Structure
- ✅ Collection Ownership Model
- ✅ Analysis Run Engine

Open GitHub Issues

- Historical Intelligence Engine
- Configuration System
- Reporting Engine
- Database Migrations
- Database Testing

Always consult GitHub before beginning new work.

---

# Development Philosophy

The project follows several principles.

## Build foundations before features.

Every new capability should rest on stable architecture.

Avoid shortcuts that create technical debt.

---

## Small iterative improvements.

Large features should be broken into manageable GitHub issues.

Each issue should produce a working improvement.

---

## SQLite is the source of truth.

Excel is only used for exports.

No business logic should depend on spreadsheets.

---

## Preserve historical information.

Historical observations should never be overwritten.

Snapshots should accumulate over time.

Historical intelligence depends upon immutable historical data.

---

## Decisions belong to the user.

DIP performs research.

The collector makes the final decision.

User decisions should never be replaced by automated logic.

---

# Architecture

Current high-level architecture

```
Tkinter UI
        │
        ▼
Application Services
        │
        ▼
Repository Layer
        │
        ▼
SQLite Database
```

Current major packages include:

- app.py
- database/
- services/
- importers/
- scoring/

Business logic should remain outside the UI wherever practical.

---

# Engineering Standards

Preferred design patterns

- Repository Pattern
- Service Layer
- Small focused classes
- Composition over inheritance
- Separation of concerns

Avoid placing significant business logic inside app.py.

---

# Git Workflow

Normal workflow

GitHub Issue

↓

Discuss design

↓

Implement

↓

Test

↓

Update documentation

↓

Update CHANGELOG

↓

Commit

↓

Close GitHub Issue

Every significant capability should have its own commit.

---

# Documentation

Documentation is considered part of the product.

Relevant documentation should be updated whenever architecture changes.

Important documents include:

- README.md
- Roadmap.md
- Architecture.md
- Database.md
- CHANGELOG.md
- Journal.md

---

# Historical Context

The project originally began as an Excel-based proof of concept.

It has since evolved into a fully database-backed desktop application.

Major architectural milestones include:

- SQLite migration
- Service layer introduction
- Collection ownership model
- Analysis Run Engine

Future work should continue building on these foundations.

---

# Long-Term Vision

The platform is expected to evolve into multiple intelligence modules.

Examples include:

- Collection Intelligence
- Market Intelligence
- Release Intelligence
- Artist Intelligence
- Label Intelligence
- Personal Intelligence

Version 0.1 intentionally avoids implementing all future capabilities.

The goal is to establish a stable platform capable of supporting them.

---

# Working Style

Development should be collaborative.

When proposing changes:

- explain the reasoning
- prefer incremental improvements
- avoid unnecessary complexity
- preserve backwards compatibility where practical

Good engineering judgement is preferred over clever code.

# Working Relationship

This project is intentionally developed collaboratively.

The user is growing as a software engineer throughout the project.

When assisting:

- Explain architectural decisions.
- Prefer teaching over simply providing code.
- Introduce one concept at a time.
- Encourage testing after each meaningful change.
- Keep commits small and purposeful.
- Keep documentation aligned with the implementation.

The aim is not only to build DIP, but also to build the engineering skills needed to maintain it over the long term.

---

# Guiding Principle

If uncertain:

Prefer maintainability over speed.

Prefer clarity over cleverness.

Prefer architecture over shortcuts.

The project is intended to exist for many years.