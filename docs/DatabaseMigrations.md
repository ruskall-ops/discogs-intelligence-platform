# Database Migrations

> **The Discogs Intelligence Platform uses a lightweight migration framework to evolve the database schema safely while preserving existing user data.**

The migration system ensures that database changes can be applied incrementally without requiring users to recreate their database.

---

# Purpose

As the platform evolves, new tables, columns, indexes and data structures will be introduced.

Rather than relying on ad hoc compatibility code, all schema changes should be implemented as versioned database migrations.

This provides:

- Safe upgrades
- Repeatable schema evolution
- Reliable version tracking
- Data preservation
- Clear database history

---

# Migration Philosophy

The migration framework follows several core principles.

Every migration should be:

- Small
- Atomic
- Idempotent where practical
- Versioned
- Easy to understand
- Safe to execute multiple times

Database migrations should never delete user data without explicit user action.

---

# Migration Structure

Migrations are stored as versioned Python modules.

```
database/
└── migrations/
    ├── base.py
    ├── runner.py
    └── versions/
        ├── v001_add_analysis_run_id.py
        ├── v002_...
        └── ...
```

Each migration exposes a single migration object derived from the common `Migration` base class.

Example:

```python
class Migration001(Migration):

    version = 1
    name = "Add analysis_run_id"

    def upgrade(self, connection):
        ...
```

---

# Migration Execution

Database migrations are executed automatically during database initialisation.

The process is:

1. Initialise the current schema.
2. Ensure the migration tracking table exists.
3. Discover available migrations.
4. Determine which migrations have already been applied.
5. Execute pending migrations in version order.
6. Record successful migrations.

Each migration is executed only once.

---

# Schema Tracking

Applied migrations are recorded in the `schema_migrations` table.

The table stores:

- Migration version
- Migration name
- Applied timestamp

This allows the platform to determine which migrations remain outstanding.

---

# Adding a New Migration

When introducing a database schema change:

1. Update `schema.sql` to represent the latest schema.
2. Create a new migration in `database/migrations/versions/`.
3. Assign the next available version number.
4. Implement the migration logic.
5. Verify the migration against both:
   - a new database
   - an existing database

Every migration should preserve user data wherever possible.

---

# Existing vs New Databases

`schema.sql` always represents the latest database schema.

New installations create the complete schema directly from `schema.sql`.

Existing databases are upgraded using versioned migrations.

This approach avoids replaying historical migrations when creating a brand-new database while still supporting safe upgrades for existing users.

---

# Design Goals

The migration framework intentionally remains lightweight.

It is designed specifically for a local SQLite desktop application and avoids introducing heavyweight external migration tools.

The framework prioritises:

- Simplicity
- Reliability
- Readability
- Maintainability
- Long-term stability

---

# Future Enhancements

Potential future improvements include:

- Migration validation reports
- Migration logging
- Data migration helpers
- Rollback support
- Migration integrity verification
- Command-line migration utilities

These features will be evaluated as the platform evolves.

---

# Guiding Principle

Database schema evolution should be deliberate, predictable and safe.

Every migration should preserve the integrity of historical data while allowing the platform to continue evolving over time.

---

## Document Information

Version: 1.0

Status: Active

Owner: Russell Friend