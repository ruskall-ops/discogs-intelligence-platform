# Changelog

All notable changes to the Discogs Intelligence Platform will be documented here.

---

# Sprint 2 – Collection Intelligence

## Intelligence Engine Foundation

- Added the versioned Collection Intelligence module protocol.
- Added ordered module registration with duplicate protection.
- Expanded the shared analysis context and standard result models.
- Added aggregate engine execution results and module lookup.
- Isolated module failures so later modules continue to execute.
- Added output validation and concise failure diagnostics.
- Preserved the existing application and scoring behaviour.
- Added focused registry, execution and failure-isolation tests.

---

# Sprint 0 – Foundation

## Documentation
- Created Vision document.
- Created Architecture document.
- Created Engineering Principles.
- Created Design Principles.
- Created Business Model.
- Created Product Positioning.
- Created Roadmap.
- Created Database design.
- Created Glossary.
- Established GitHub project structure.
- Established development workflow.

---

# Sprint 1 – Core Platform

## Database Refactor
- Refactored SQLite into a modular database package.
- Separated connection management from repository logic.
- Externalised SQL schema.
- Improved project structure.
- Updated `.gitignore` for local databases and generated files.

### Documentation

- Documented the Collection Ownership Model.
- Clarified that Discogs CSV exports do not provide unique identifiers for individual owned copies.
- Introduced the architectural distinction between Imported Facts and User Knowledge.
