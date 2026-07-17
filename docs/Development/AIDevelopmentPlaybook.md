# AI Development Playbook

## Purpose

This document captures the workflow and prompt engineering practices used to develop the Discogs Intelligence Platform (DIP) with AI assistance.

Its purpose is to ensure every implementation is:

- consistent
- reviewable
- maintainable
- aligned with the project's engineering standards

This playbook should be followed whenever ChatGPT Work (or another AI coding assistant) is used to implement a feature.

---

# Development Philosophy

AI is a development assistant.

It is **not** the project architect.

Architecture decisions remain deliberate and human-led.

The implementation should always follow:

- `DevelopmentStandard.md`
- the Roadmap
- the Vision
- existing architectural patterns

AI should extend the architecture rather than invent new ones.

---

# Standard Workflow

Every feature follows the same lifecycle.

```text
Idea
 ↓
Design
 ↓
Implementation Brief
 ↓
AI Implementation
 ↓
Import
 ↓
Review
 ↓
Testing
 ↓
Pull Request
 ↓
Merge
```

Skipping review is discouraged.

---

# Before Writing a Prompt

Before asking AI to implement a feature:

- Clearly define the problem.
- Decide what version of the roadmap it belongs to.
- Define the scope.
- Decide what is explicitly out of scope.
- Consider how it fits existing architecture.

Do not ask AI to invent project direction.

---

# Implementation Brief Template

Every implementation brief should include:

## Objective

What is being built?

## Scope

Exactly what should be implemented.

## Out of Scope

What should not be implemented.

## Architectural Constraints

Examples:

- Use existing Intelligence Engine.
- Use IntelligenceContext.
- Return IntelligenceResult.
- No UI coupling.
- No database access.
- No Discogs API calls.

## Configuration

Describe any required configuration objects.

## Testing

Describe expected automated tests.

## Documentation

Describe required documentation updates.

---

# Prompting Principles

Good prompts are:

- specific
- constrained
- architectural
- deterministic

Avoid vague requests such as:

> "Improve this."

Prefer:

> "Implement this module using the existing IntelligenceModule architecture."

---

# Preferred AI Behaviour

AI should:

- reuse existing patterns
- avoid unnecessary abstraction
- produce readable code
- favour explicitness
- explain assumptions

AI should not:

- introduce new frameworks
- redesign architecture
- invent requirements
- silently remove functionality

---

# Import Workflow

After downloading the implementation:

1. Extract into the local Work directory.
2. Run:

```bash
./scripts/import-work.sh
```

3. Review all imported files.

Never commit imported code without review.

---

# Review Workflow

Review every implementation before committing.

Typical review areas:

- Architecture
- Separation of concerns
- Explainability
- Configuration
- Testing
- Documentation

Review both new and modified files.

---

# Validation Checklist

Always run:

```bash
bash -n scripts/import-work.sh
python3 -m pytest
git diff --check
```

Every command should pass before committing.

---

# Git Workflow

Use feature branches.

Typical lifecycle:

```text
main
 │
 ├── feature/...
 ├── docs/...
 └── fix/...
```

Keep Pull Requests focused.

One purpose per Pull Request.

---

# Pull Request Guidelines

Every Pull Request should describe:

- Summary
- Included functionality
- Out of scope
- Validation performed

Review before merging.

---

# Lessons Learned

## Small prompts produce better implementations

Large feature requests often produce inconsistent architecture.

Smaller vertical slices consistently produce higher quality code.

---

## Explicit constraints improve quality

Always specify:

- architectural boundaries
- configuration expectations
- testing expectations
- documentation expectations

---

## Review every AI change

Treat AI-generated code exactly like code written by another developer.

Nothing should bypass review.

---

## Keep commits small

Small commits:

- review more easily
- revert more safely
- document project evolution

---

## Explainability is a feature

The platform should never produce opaque intelligence.

Every module should explain its reasoning.

---

## Prefer consistency over novelty

Reuse existing patterns whenever possible.

Consistency is more valuable than cleverness.

---

# Continuous Improvement

Whenever a better workflow is discovered:

- update this document
- refine future implementation briefs
- improve the development process

The objective is not merely to build better software.

The objective is to build better software **more consistently**.

# Repository First

Before implementing a feature, AI should understand the repository.

Review:

- Vision
- Roadmap
- Development Standard
- Existing architecture
- Similar intelligence modules

New code should feel like it belongs in the repository rather than looking AI-generated.

The best implementation is one that another developer cannot distinguish from hand-written project code.