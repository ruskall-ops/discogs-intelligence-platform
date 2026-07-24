# Database Design

> **The database is the historical memory of the Discogs Intelligence Platform.**

---

# Purpose

The purpose of the database is to provide a reliable, explainable and historically accurate record of collection data, marketplace intelligence and user decisions.

Rather than acting purely as storage, the database preserves the evolution of both the collection and the market over time.

Historical information is considered a core feature of the platform.

---

# Design Philosophy

The database should:

- Preserve historical information.
- Never overwrite valuable observations.
- Remain lightweight and easy to understand.
- Support future expansion.
- Favour clarity over unnecessary optimisation.
- Be fully explainable.

The database should always support the platform philosophy:

> **Automate the research, not the collecting decision.**

---

# Technology

Current database engine:

**SQLite**

SQLite has been selected because it provides:

- Zero configuration
- Excellent reliability
- Cross-platform compatibility
- Strong performance for desktop applications
- Easy backup and portability

Should future requirements exceed SQLite's capabilities, the architecture should allow migration with minimal disruption.

---

# Core Principles

## Historical First

Historical information should be preserved wherever practical.

Snapshots should be appended rather than overwritten.

The platform should be able to answer questions such as:

- What changed?
- When did it change?
- Why did it change?

---

## Immutable Market Data

Marketplace observations represent historical facts.

Once captured they should not normally be modified.

---

## Explainable Intelligence

Every score should be traceable back to the underlying market data used to generate it.

---

## Separation of Responsibilities

Each table should have one clearly defined responsibility.

Avoid mixing:

- marketplace data
- user decisions
- calculated intelligence
- application configuration

within the same table.

---

# Database Structure

## schema_migrations

Tracks database schema versions.

Purpose:

Allow controlled evolution of the database structure.

---

## analysis_runs

Represents one complete intelligence refresh.

Example information:

- Started
- Completed
- Duration
- Success
- Source

This allows every snapshot and score to be linked back to a specific analysis run.

---

## releases

Represents the Discogs release.

Contains information that identifies the release itself.

Examples:

- Artist
- Title
- Label
- Catalogue Number
- Format
- Release Date

One release may exist many times within a collection.

---

## collection_items

Represents an owned copy of a release.

Future examples include:

- Purchase date
- Purchase price
- Media condition
- Sleeve condition
- Collection folder
- Personal notes

Multiple owned copies may reference the same release.

---

## market_snapshots

Historical marketplace observations.

Examples:

- Wants
- Haves
- Lowest Price
- Copies For Sale
- Currency

Snapshots should never replace previous observations.

---

## score_snapshots

Historical calculated intelligence.

Examples:

- Value Score
- Demand Score
- Liquidity Score
- Momentum Score
- Opportunity Score

Historical scores allow trends to be analysed over time.

---

## decisions

Stores user decisions independently of marketplace data.

Examples:

- Keep
- Sell
- Review

Also includes:

- Personal notes
- Protected status
- Miss rating

---

## app_settings

Stores application configuration.

Examples:

- User preferences
- Refresh frequency
- Interface options

---

## projects

Stores normalized Project application state:

- `project_id` — stable text primary key;
- `name` — required display name;
- `description` — required presentation-ready description;
- `last_opened_order` — nullable positive application-controlled sequence;
- `insertion_order` — required unique positive sequence used for deterministic
  listing.

## project_state

Stores exactly one row with `singleton_id = 1`. Its nullable
`active_project_id` is a foreign key to `projects.project_id` with restricted
deletion. Active state is separate from Project content.

Migration version 4 adds both tables. A fresh database includes the same schema.
The first desktop composition creates `Current Collection` only when absent and
does not replace an existing Project or active selection.

---

# Entity Relationships

```text
analysis_runs
      │
      ├──────────────┐
      │              │
market_snapshots   score_snapshots
      │              │
      └──────┬───────┘
             │
         releases
             │
             │
      collection_items
             │
        decisions
```

---

# Historical Strategy

The platform should favour preserving information rather than replacing it.

Examples:

Market snapshots

✔ Append

Scores

✔ Append

User decisions

✔ Update

Configuration

✔ Update

---

# Future Expansion

The current database is designed to support future modules including:

- Collection Intelligence
- Market Intelligence
- Release Intelligence
- Personal Intelligence
- Dealer Toolkit
- AI Collection Assistant

Future functionality should be implemented through new tables where appropriate rather than overloading existing structures.

---

# Success

A successful database should:

- Preserve history.
- Remain understandable.
- Be easy to extend.
- Provide reliable performance.
- Support explainable intelligence.

## Design Principle

The database distinguishes between two categories of information.

### Imported Facts

Information obtained directly from Discogs or other external systems.

These records always reflect the capabilities and limitations of their source.

### User Knowledge

Information created and maintained by the user.

Examples include:

- Purchase history
- Manual valuations
- Personal notes
- Cleaning records
- Storage locations
- Insurance information
- Custom tags

User Knowledge should never be overwritten by future imports.

Project persistence does not include collection refresh state, open-window
state, workspace navigation, or session restoration.

This separation allows DIP to safely refresh imported data while preserving all user-generated information.


The database is considered the foundation upon which every other platform capability is built.

---

## Document Information

Version: 1.0

Status: Active

Owner: Russell Friend
