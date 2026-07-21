# AI Development Playbook

> **This playbook defines the standard approach for using AI-assisted development within the Discogs Intelligence Platform (DIP).**

It complements the project's `DevelopmentStandard.md` by describing how AI should be used throughout the software development lifecycle.

The objective is to ensure AI consistently produces high-quality, deterministic, explainable and maintainable code that aligns with the long-term architecture of the platform.

---

# Philosophy

AI is an engineering assistant, not an autonomous developer.

Its purpose is to accelerate implementation while remaining under human architectural control.

AI should:

- accelerate implementation
- reduce repetitive work
- improve documentation
- improve testing
- suggest improvements
- never replace engineering judgement

Every implementation remains subject to review before being committed.

---

# Core Principles

Every AI-generated implementation should:

- Follow the Development Standard.
- Respect the existing architecture.
- Extend existing patterns rather than introducing new ones.
- Be deterministic.
- Be explainable.
- Be fully tested.
- Be fully documented.
- Avoid unnecessary complexity.

AI should optimise for long-term maintainability rather than short-term speed.

---

# Repository-First Development

Before implementing any feature, AI should understand the existing repository.

Implementation should always begin by reviewing:

- `docs/Development/DevelopmentStandard.md`
- `docs/Development/AIDevelopmentPlaybook.md`
- `docs/Roadmap.md`
- Existing module implementations
- Existing tests
- Existing architecture

Features should extend the platform rather than creating parallel implementations.

---

# Vertical Slice Development

Every feature should be delivered as a complete vertical slice.

A vertical slice normally includes:

- implementation
- configuration
- tests
- documentation
- integration
- registration

User interface work should only be included when explicitly within scope.

Small complete features are preferred over partially completed large features.

---

# Standard Implementation Workflow

Each implementation should follow the same sequence.

## 1. Understand

Review:

- Development Standard
- Roadmap
- Existing implementation
- Existing tests
- Existing architecture

Clarify:

- objectives
- scope
- non-goals

---

## 2. Implement

Implement only the requested feature.

Avoid speculative functionality.

Reuse existing abstractions wherever possible.

---

## 3. Test

Every feature should include appropriate tests.

Tests should cover:

- happy path
- edge cases
- invalid input
- deterministic behaviour
- configuration
- failure isolation

Existing tests should continue to pass unchanged.

---

## 4. Document

Documentation should be updated where appropriate.

Potential updates include:

- README
- CHANGELOG
- Roadmap
- Intelligence module documentation
- Architecture documentation

Documentation should describe behaviour rather than implementation details where possible.

---

## 5. Package

Implementation should be packaged into an importable ZIP preserving the repository structure.

The ZIP should contain:

- new files
- modified files
- tests
- documentation

The repository root should be preserved exactly.

---

# Standard Feature Prompt Template

A typical implementation request should include:

- objective
- scope
- repository standards
- existing architecture
- implementation constraints
- testing requirements
- documentation requirements
- packaging requirements

The prompt should also clearly state:

## In Scope

Features that should be implemented.

## Out of Scope

Features that should not be implemented.

Explicit scope reduces unnecessary implementation and improves consistency.

---

# Git Workflow

Every feature should follow the same Git workflow.

## Create Feature Branch

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feature/<feature-name>
```

---

## Generate Work

Generate the implementation using ChatGPT Work.

---

## Import

Import using:

```bash
./scripts/import-work.sh
```

---

## Review

Review all imported changes before committing.

---

## Validate

Run:

```bash
pytest
git diff --check
git status
```

---

## Commit

Example:

```bash
git commit -m "feat: implement historical intelligence"
```

---

## Push

```bash
git push
```

---

## Create Pull Request

Review before merge.

---

## Merge

Merge only after successful review.

---

# Post-Import Review Checklist

Every AI-generated implementation should be reviewed before commit.

## Documentation

Review:

- README.md
- Roadmap.md
- CHANGELOG.md
- Existing module documentation

Check for:

- stale documentation
- accidental removals
- overwritten improvements
- missing references

---

## Existing Code

Review:

- registry changes
- public exports
- existing modules
- existing tests

Confirm:

- no regressions
- no weakened tests
- no unnecessary changes

---

## New Feature

Review:

- architecture
- implementation
- determinism
- explainability
- configuration
- tests
- documentation

---

## Validation

Run:

```bash
pytest
git diff --check
git status
```

The implementation should only be committed after all validation succeeds.

---

# Common Work Import Issues

Experience has shown that AI-generated ZIP imports occasionally contain repository drift.

Common issues include:

## Documentation Regression

Older versions of:

- README
- Roadmap
- CHANGELOG

may overwrite newer repository versions.

Always compare documentation before accepting imported changes.

---

## Registry Updates

Ensure new modules are intentionally registered.

Review:

- default registry
- public exports
- configuration

---

## Existing Tests

Ensure existing tests have not been weakened.

New functionality should expand the test suite rather than reduce coverage.

---

## Missing ZIP Artefacts

If ChatGPT Work fails to provide downloadable ZIP artefacts:

- use the browser version of ChatGPT
- regenerate the ZIP
- verify the download before importing

---

# Prompting Best Practices

Implementation prompts should:

- clearly define the objective
- reference the Development Standard
- reference the Roadmap
- identify relevant existing modules
- define implementation constraints
- define testing requirements
- define documentation requirements
- define packaging requirements

Clear prompts consistently produce better implementations.

---

# Definition of Done

A feature is complete when:

- implementation is finished
- tests pass
- documentation is updated
- architecture has been reviewed
- import has been reviewed
- validation passes
- pull request is approved
- feature is merged

Completion is measured by quality rather than speed.

---

# Lessons Learned

This section should evolve as the project matures.

Current lessons include:

- Always review imported documentation for stale content.
- Preserve newer repository documentation when Work imports contain older copies.
- Review README, Roadmap and CHANGELOG before committing.
- Review registry changes carefully.
- Ensure existing tests have not been weakened.
- Prefer browser-based ChatGPT Work if ZIP artefacts are missing.
- Package implementations as complete vertical slices.
- Small deterministic features are easier to review than large multi-feature implementations.

This section should continue to grow as new patterns and improvements are identified.

---

# Continuous Improvement

The playbook is a living document.

As new workflows, tooling or lessons emerge, they should be incorporated into this document.

The objective is continuous improvement of both the platform and the development process itself.

---

## Guiding Principle

> **Use AI to accelerate engineering, never to replace engineering discipline.**

AI should consistently help produce software that is:

- deterministic
- explainable
- maintainable
- well tested
- well documented
- architecturally consistent

Every feature should strengthen the platform rather than simply add functionality.

---

## Document Information

Version: 1.0

Status: Active

Owner: Russell Friend