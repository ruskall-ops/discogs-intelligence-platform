# Roadmap

> **The Discogs Intelligence Platform roadmap defines the planned evolution of the platform from its initial foundations through to its long-term vision.**

The roadmap is intended to provide direction rather than fixed deadlines. Development priorities may change as new ideas emerge, user feedback is received, and the platform matures.

---

# Development Philosophy

The Discogs Intelligence Platform is developed incrementally.

Each release should:

- Deliver meaningful value.
- Improve the overall platform.
- Build upon a stable foundation.
- Avoid unnecessary complexity.
- Remain aligned with the core vision.

New ideas are encouraged, but they should be documented and evaluated before becoming scheduled work.

---

# Platform Evolution

The platform evolves through three complementary intelligence layers.

## Personal Intelligence

Insights focused on the individual collector.

## Marketplace Intelligence

Insights focused on historical market behaviour.

## Platform Intelligence

Future anonymous, aggregated intelligence derived from community behaviour.

Platform Intelligence is intentionally not scheduled and will be introduced only once sufficient historical data and user adoption make it meaningful.

---

# Business Model

DIP follows a freemium intelligence model.

The free platform provides genuine value through collection intelligence and historical tracking.

Premium subscriptions unlock deeper intelligence, automation and analysis.

As adoption grows, anonymous aggregate data improves the quality of platform-wide intelligence, creating a positive feedback loop between community growth and insight quality.

---

# Current Sprint

## Sprint 2

### Objective

Build Collection Intelligence.

Primary focus:

- Collection Intelligence Engine foundation ✅
- Collection Health vertical slice (Issue #18) ✅
- Interactive Dashboard view-model foundation ✅
- Collection Health dashboard card ✅
- Hidden Gems intelligence module ✅
- Desktop dashboard integration
- Collection Health
- Hidden Gems dashboard integration
- Historical Trends
- Collection Analytics
- Dashboard drill-down
- Explainable intelligence

Current GitHub Milestone:

**Version 0.2 – Collection Intelligence**


---

# Planned Releases

---

## Version 0.1 – Core Platform

**Status**

✅ Released

### Goal

Create the engineering foundation for the entire platform.

Completed deliverables:

- Database Foundation
- Import Engine
- Historical Intelligence Engine
- Reporting Framework
- Configuration System
- Database Migrations
- Automated Test Suite


This version prioritises stability over features.

---

## Version 0.2 – Collection Intelligence

Version 0.2 expands the platform from a collection reporting tool into a true collection intelligence platform.

The focus is on producing transparent, explainable insights that help collectors better understand their collection without making purchasing or selling decisions.

### Foundation ✅

The following capabilities have been completed:

- Collection Intelligence Engine
- Collection Health
- Interactive Dashboard
- Hidden Gems Intelligence
- Development Standards
- AI Development Playbook

These components provide the foundation for all future intelligence modules.

---

# Intelligence Capabilities

## Historical Intelligence (Next Priority)

Historical Intelligence introduces the concept of analysing change over time.

Rather than examining only the current collection state, this capability compares historical snapshots to identify meaningful trends and changes.

Planned capabilities include:

- Collection Trends
- Collection Growth
- Value Trends
- Artist Trends
- Label Trends
- Genre Trends
- Historical Collection Summary

Examples include:

- Highest value increases
- Largest value decreases
- Fastest growing artists
- Largest collection growth
- Collection composition changes

This capability provides the historical foundation for many future intelligence modules.

---

## Intelligence History

The platform already stores historical snapshots.

This capability introduces historical intelligence by preserving the outputs of intelligence modules over time.

Examples:

- Collection Health history
- Hidden Gem score history
- Collection value history
- Future intelligence module history

This enables users to understand how intelligence evolves rather than viewing isolated point-in-time results.

---

## Market Intelligence

Market Intelligence analyses changes occurring within the wider Discogs marketplace.

Initial scope includes:

- Market Movers
- Demand changes
- Supply changes
- Marketplace activity

Future versions may introduce additional marketplace analytics while maintaining explainable outputs.

---

# Explorer

## Explorer Framework

Shared framework providing:

- Filtering
- Sorting
- Searching
- Grouping
- Paging

The Explorer Framework provides reusable infrastructure for future dashboards and user interfaces.

---

## Collection Intelligence Explorer

The Collection Intelligence Explorer provides an enriched view of individual releases.

Each release will gradually surface intelligence generated throughout the platform.

Examples include:

- Collection Health
- Hidden Gems
- Historical Trends
- Market Intelligence
- Future intelligence modules

The explorer acts as a window into the platform's intelligence rather than simply listing collection items.

---

# Developer Experience

The project continues to improve its internal development workflow.

Completed improvements include:

- Development Standard
- AI Development Playbook
- ChatGPT Work import workflow
- Automated testing
- Pull Request workflow
- Engineering documentation

These improvements increase long-term maintainability and ensure consistent implementation quality.

---

# Design Principles

Every capability introduced during Version 0.2 should follow the project's core philosophy:

> **Automate the research, not the decision.**

The platform should:

- produce explainable intelligence
- remain deterministic
- avoid opaque scoring
- never recommend buying or selling
- support research rather than replace judgement

---

## Version 0.4 – Decision Support

**Status**

📅 Planned

### Goal

Personalise the platform around the collector.

Expected capabilities:

- Personal watchlists
- Wishlist intelligence
- Personal alerts
- Custom dashboards
- Personal recommendations
- Collection goals

---

# Future Modules

The following modules have been defined but are intentionally not scheduled for development.

They will be evaluated as the platform evolves.

| Module | Status |
|----------|--------|
| Release Intelligence | 📝 Defined |
| Market Discovery | 📝 Defined |
| Mobile Companion | 🌱 Idea |
| Dealer Toolkit | 🌱 Idea |
| AI Collection Assistant | 🌱 Idea |
| Community Intelligence | 💭 Vision|
| Platform Intelligence| 💭 Vision|
| Trend Detection | 🌱 Idea |
| Alert Engine| 🌱 Idea |
| Portfolio Analytics | 📝 Defined|


---

# Module Lifecycle

Future modules typically evolve through the following stages:

💭 Vision

↓

🌱 Idea

↓

📝 Defined

↓

📅 Planned

↓

🚧 In Development

↓

✅ Released

---

# Decision Making

When new ideas emerge they should first be classified.

| Type | Destination |
|---------|-------------|
| Architecture decision | `/docs/decisions/` |
| Future capability | `/docs/FutureModules/` |
| Product roadmap | `Roadmap.md` |
| Development task | GitHub Issue |
| Immediate bug | GitHub Issue |
| Major engineering decision | ADR |

This process ensures ideas are captured without interrupting the current sprint.

---

# Long-Term Vision

The long-term ambition is to build the leading intelligence platform for vinyl collectors.

Over time, the platform should become more valuable not simply because more features are added, but because its historical knowledge and anonymous community intelligence continually improve.

The long-term competitive advantage of DIP lies in transforming historical data into explainable intelligence.

Rather than acting solely as a collection manager, DIP aims to become an evidence-based decision support platform that helps collectors:

- Understand their collection.
- Understand the wider market.
- Discover emerging opportunities.
- Preserve historical intelligence.
- Make more informed collecting decisions.

The platform will always remain faithful to its core philosophy:

> **Automate the research, not the collecting decision.**

---

# Success Criteria

Success is measured by:

- Platform quality
- User value
- Explainable intelligence
- Reliable historical data
- Sustainable architecture
- Long-term maintainability

rather than the speed at which features are delivered.

---

# Guiding Principle

Ideas should never be lost.

Features should never be rushed.

The roadmap exists to ensure the platform evolves deliberately, sustainably and consistently over time.

---

## Document Information

Version: 1.1

Status: Active

Owner: Russell Friend
