# Glossary

---

# Purpose

This glossary defines the terminology used throughout the Discogs Intelligence Platform.

Using consistent language improves communication, documentation and software design.

Every defined term should have one clear meaning throughout the project.

---

# Analysis Run

A single execution of the platform that retrieves market data, updates historical snapshots and recalculates intelligence.

Every Analysis Run has its own timestamp and summary.

---

# Market Snapshot

A historical record of marketplace information for a release at a specific point in time.

Examples include:

- Lowest Price
- Median Price
- Highest Price
- Number For Sale
- Number Wanted

Snapshots are immutable.

---

# Historical Database

The collection of all historical snapshots stored by the platform.

Historical information is never overwritten.

---

# Opportunity Engine

The component responsible for identifying records that deserve the collector's attention.

It classifies records based on objective market evidence.

---

# Opportunity Score

A weighted score representing how interesting a record is for review.

The score is transparent and explainable.

It is never a black-box value.

---

# Hidden Gem

A record identified as having strong market characteristics that may not yet be widely recognised.

Hidden Gems should always be supported by evidence.

---

# Weekend Listings

A curated shortlist of records that may be worth considering for sale.

The platform never recommends automatic selling.

Weekend Listings are suggestions for review.

---

# Collector DNA

A long-term profile describing the collector's interests and behaviour.

Examples include:

- Favourite genres
- Favourite labels
- Favourite artists
- Typical purchase prices
- Selling behaviour

Collector DNA personalises recommendations without replacing objective analysis.

---

# Protected Record

A record that the collector has chosen never to sell.

Protected Records are excluded from selling recommendations.

---

# Recommendation

A record highlighted by the platform because market evidence suggests it deserves attention.

Recommendations should always explain:

- Why this record?
- Why now?

---

# Why Now?

An explanation describing why a recommendation appears during the current Analysis Run.

Typical reasons include:

- Supply reduction
- Demand increase
- Price movement
- Market momentum
- Scarcity changes

---

# Market Momentum

A measure describing whether market demand is:

- increasing
- stable
- decreasing

Momentum is calculated using historical information.

---

# Scarcity

A measure of how difficult a record is becoming to obtain.

Scarcity is based on market availability rather than subjective rarity.

---

# Collection Intelligence

The collection of analyses relating specifically to the user's collection.

Examples include:

- Collection value
- Hidden Gems
- Weekend Listings
- Collection Health

---

# Market Intelligence

Analysis relating to the wider marketplace rather than the user's individual collection.

Examples include:

- Demand trends
- Genre movement
- Label performance
- Supply changes

---

# Personal Intelligence

Insights influenced by the collector's own preferences and previous decisions.

Personal Intelligence never replaces objective market analysis.

---

# Dashboard

The primary overview screen of the platform.

The Dashboard surfaces the most important intelligence generated during the latest Analysis Run.

---

# Confidence Score

An indication of how reliable the available evidence is for a recommendation.

Confidence is separate from Opportunity Score.

---

# Repository

A software component responsible for reading and writing a specific area of the SQLite database.

Repositories isolate database access from the rest of the application.

---

# ADR

Architecture Decision Record.

A short document describing an important architectural decision and the reasons behind it.

---

# Sprint

A focused period of development targeting a defined set of issues.

---

# Milestone

A major release goal consisting of multiple related issues.

Examples include:

- Version 0.1 – Core Platform
- Version 0.2 – Collection Intelligence

---

# Guiding Principle

If a new term is introduced during development, it should be added to this glossary before being widely used.

Consistent language creates consistent software.

---

## Document Information

Version: 1.0

Status: Active

Last Updated: July 2026

Owner: Russell Friend