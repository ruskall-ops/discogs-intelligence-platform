# ADR-0001

## Title

Use SQLite as the primary datastore.

## Status

Accepted

## Context

DIP requires a lightweight embedded database suitable for a desktop application.

## Decision

SQLite will be used.

## Consequences

Advantages

- no installation
- fast
- reliable
- portable
- widely supported

Disadvantages

- single-user only
- not intended for cloud scale

These trade-offs are acceptable for the current vision.