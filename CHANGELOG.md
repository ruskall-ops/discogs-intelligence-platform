# Changelog

All notable changes to the Discogs Intelligence Platform will be documented here.

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