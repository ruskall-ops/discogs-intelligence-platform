# Platform Architecture

## Purpose

This document describes the high-level architecture of the Discogs Intelligence Platform (DIP).

Unlike the software architecture documentation, which focuses on implementation details, this document explains how the major platform components interact to transform collection data into meaningful, explainable intelligence.

It is intended to provide a stable architectural vision that remains valid regardless of programming language, framework or user interface technology.

---

# Architectural Philosophy

The Discogs Intelligence Platform is designed around a simple principle:

> Transform collection data into explainable intelligence that helps collectors make better decisions.

The platform deliberately separates:

- Data acquisition
- Data storage
- Intelligence generation
- Presentation
- User decisions

This separation keeps the platform modular, testable and extensible.

---

# Platform Layers

The platform is organised into a series of logical layers.

```
                User Interface
                       │
                       ▼
             Presentation Layer
                       │
                       ▼
           Collection Intelligence
                       │
                       ▼
          Historical Snapshot Engine
                       │
                       ▼
             Marketplace Intelligence
                       │
                       ▼
                Data Management
                       │
                       ▼
                  Data Sources
```

Each layer has a single responsibility.

---

# Data Sources

The platform is intentionally independent of any single data provider.

Current data sources include:

- Discogs Collection Export
- Discogs Marketplace

Future data sources may include:

- MusicBrainz
- Bandcamp
- Popsike
- eBay
- Whatnot
- Barcode Scanners
- User spreadsheets
- Public APIs

New data sources should integrate without requiring changes to the intelligence layer.

---

# Data Management

The Data Management layer is responsible for:

- importing collection data
- validating data
- normalising records
- storing historical snapshots
- managing configuration
- maintaining data integrity

This layer does not perform intelligence or recommendations.

Its purpose is to provide reliable, consistent data for higher platform layers.

---

# Marketplace Intelligence

Marketplace Intelligence enriches collection data using external market information.

Examples include:

- estimated values
- sales history
- marketplace activity
- demand indicators
- supply indicators

This layer describes the market.

It does not analyse the user's collection.

---

# Historical Snapshot Engine

Historical snapshots are a core architectural component.

Every intelligence run preserves a snapshot of:

- collection composition
- marketplace information
- calculated intelligence
- user decisions (where appropriate)

Historical snapshots allow the platform to answer questions such as:

- What changed?
- What is changing?
- What trends are emerging?

Rather than only displaying current information.

---

# Collection Intelligence

Collection Intelligence is the heart of the platform.

It transforms raw data into meaningful, explainable insights.

Examples include:

- Collection Health
- Hidden Gems
- Market Movers
- Collection Trends
- Weekly Intelligence Reports
- Future Recommendation Engines

Each intelligence module is independent and reusable.

Modules should explain their conclusions rather than simply producing scores.

---

# Experience Layer

The Experience Layer makes intelligence accessible to users.

Examples include:

- Dashboard
- Collection Explorer
- Weekly Reports
- Release Intelligence
- Future Mobile Companion
- Future AI Collection Assistant

Presentation components consume intelligence.

They do not calculate it.

This ensures consistent behaviour throughout the platform.

---

# User Decisions

A key design principle of DIP is:

> Automate the research, not the decision.

The platform provides intelligence.

Users retain complete control over:

- purchases
- sales
- collection management
- recommendations

The platform never executes decisions automatically.

---

# Extensibility
```