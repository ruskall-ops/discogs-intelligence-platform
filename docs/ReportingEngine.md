# Reporting Engine

> **The Reporting Engine transforms platform intelligence into structured, human-readable reports.**

---

# Purpose

The Reporting Engine provides a presentation layer over the Discogs Intelligence Platform.

It combines information from multiple services into a single structured report without duplicating business logic.

The Reporting Engine does **not** calculate marketplace intelligence itself. Instead, it presents information already produced by existing services.

---

# Architecture

The reporting pipeline follows this flow:

```text
Database
      ↓
Historical Intelligence Service
      ↓
Reporting Service
      ↓
IntelligenceReport
      ↓
Renderer
      ↓
Output
```

Business logic remains inside the service layer.

Rendering logic remains inside renderer modules.

The user interface simply requests report generation.

---

# Components

## ReportingService

Location:

```text
services/reporting_service.py
```

Responsibilities:

- Gather platform intelligence
- Build a structured report model
- Reuse existing services
- Avoid presentation concerns

---

## IntelligenceReport

Location:

```text
reports/models.py
```

Represents a complete report independent of output format.

Current sections include:

- Collection summary
- Latest analysis run
- Historical comparison
- Marketplace movers

---

## Markdown Renderer

Location:

```text
reports/markdown.py
```

Converts an `IntelligenceReport` into Markdown.

No database access occurs during rendering.

---

# Current Report Contents

Version 0.1 includes:

- Report title
- Generated timestamp
- Collection summary
- Latest completed analysis run
- Historical comparison summary
- Changed / unchanged / new / missing counts
- Top price movers
- Top demand movers
- Top scarcity movers

If insufficient historical data exists, the report explains this gracefully.

---

# Design Principles

The Reporting Engine should remain:

- Independent of Tkinter
- Independent of database queries during rendering
- Deterministic
- Explainable
- Easy to extend

---

# Future Renderers

The report model is intentionally independent of output format.

Future renderers may include:

- HTML
- PDF
- Excel
- Email
- Web dashboard
- REST API responses

All renderers should consume the same `IntelligenceReport` model.

---

# Future Enhancements

Possible future report sections include:

- Opportunity Score rankings
- Decision summaries
- Watchlist movement
- Price trend charts
- Collection value history
- AI-generated commentary

These features are outside the scope of Version 0.1.

---

# Guiding Principle

The Reporting Engine prepares data once and renders it many ways.

Business logic should never be duplicated between renderers.

---

## Document Information

Version: 1.0

Status: Active

Owner: Russell Friend