# Discogs Intelligence Platform

Read `docs/vision.md` and `docs/Development/AI_Development_Playbook.md` before
changing DIP. Read the architecture and local documentation for the area being
changed. Intelligence History, execution, querying and comparison require
`docs/IntelligenceHistory.md` and `docs/PersistenceArchitecture.md`; Marketplace
work requires `docs/MarketplaceArchitecture.md`.

## Product and architecture

- Automate research, not collecting decisions. Explain evidence, scores,
  changes and uncertainty; never automate trading, purchasing or selling.
- Preserve the dependency direction: domain models/services, application
  orchestration, repository contracts, persistence adapters, SQLite.
  Presentation consumes application-facing models and services.
- Domain code uses typed models, validates stable invariants, prefers frozen
  dataclasses and immutable nested collections, and is deterministic. It must
  not import SQLite, concrete persistence adapters, migrations or UI modules.
- Application services coordinate engines, repositories, lifecycle, history
  recording/querying and comparison through protocols and abstractions. They
  must not instantiate concrete SQLite repositories.
- Intelligence modules consume the established context and return typed,
  deterministic results with canonical module IDs and explicit versions.
  They do not persist, query SQLite or contain UI concerns. Do not replace
  informative independent dimensions with one opaque overall score.
- Dashboard and Explorer remain thin: request explicit application/view models,
  select components, format values, render states/errors. Presentation must not
  calculate intelligence, compare historical runs, generate domain conclusions,
  execute SQL, query storage, acquire provider data or control transactions.
- Current Collection is the one owned collection. A Project is a workspace
  concept and must not become a collection partition or ownership key.
- Preserve missing values distinctly from genuine zero, authoritative Decimal
  values, and integer numerators/denominators. Presentation rounding must not
  change domain values.
- Provider clients are constructed lazily. Navigation, presentation, startup
  and read-only inspection must not contact a provider.

## Intelligence History and comparison

- History preserves immutable observations: one run per completed orchestrated
  execution and one record per completed module result, with no partial
  execution persistence. Use append-only repository APIs, deterministic record
  ordering, explicit engine/module versions, optional collection snapshot
  linkage, strict reconstruction/validation and storage-independent models.
- Unsaved history models use `None` for database-allocated identifiers. Never
  silently remap objects claiming existing persistent IDs.
- The comparison engine compares complete historical executions; it must not
  recalculate intelligence. Keep it deterministic and storage-independent,
  align canonical module IDs, and detect added/removed modules.
- Dispatch through a registry of module comparers. Module-specific comparison
  logic belongs outside the central engine. Return immutable structured models;
  generic comparison compares values without interpretation. Specialised
  comparers own domain deltas/explanations, never Dashboard wording/formatting.

## Repositories, serialization and ordering

- Repository protocols are narrow, storage-independent and domain-oriented,
  with explicit ordering and absence semantics. Implementations reconstruct
  validated domain models rather than raw rows, reject malformed storage,
  preserve deterministic ordering and propagate meaningful failures. Do not
  add business logic or speculative query methods.
- Singular absence generally returns `None`; plural absence returns an empty
  immutable collection. Preserve established local contracts where they differ.
- Use the approved deterministic serialization boundary and explicit type
  registries/allow-lists. No arbitrary-object serializer or duplicated
  repository serialization logic. Preserve tuple semantics, enum types, dates,
  datetimes, finite decimals, timedeltas and approved domain dataclasses.
- Reject unknown tags/types, NaN, infinity, malformed payloads and duplicate
  JSON keys where relevant. Never silently repair corrupted persistence state.
- Preserve exact datetime semantics. Normalize aware values consistently for
  ordering; treating naive values as UTC for ordering requires documentation,
  and reconstructed naive values must remain naive.
- Every ordered query defines complete deterministic ordering with stable
  secondary keys such as persistent IDs; timestamp-only ordering is insufficient.
- Identical inputs and versions produce identical results. Do not depend on
  unordered sets, incidental dictionary order, row order without `ORDER BY`,
  runtime subclass discovery or display labels as identifiers. Use canonical
  IDs, explicit versions and injectable clocks where tests require time control.

## Migrations, validation and errors

- Fresh databases use the current schema; existing databases use ordered,
  deterministic, versioned migrations. Both paths must produce equivalent schemas.
- Migrations are atomic, recorded only after success, and roll back schema,
  data and version recording on failure. Use savepoints inside outer transactions.
- Migration tests start from genuine previous-version schemas, never the latest
  schema masquerading as an upgrade. Maintain fresh-schema/migration parity tests.
- Validate public boundaries and reject booleans where integers are required.
  Use clear `TypeError`/`ValueError` behavior consistent with existing code.
  Do not swallow failures; preserve useful exception causes when translating
  errors, and avoid broad wrapping that hides the original failure.

## Compatibility and data safety

- Existing databases, sessions, exports and historical records are compatibility
  boundaries. Never silently normalize or reinterpret retained values.
- Do not change package versions, schemas, migration sets, dependency contracts,
  public filenames or compatibility exports without explicit authorization.
- Do not access personal or ignored databases. Use synthetic databases in
  disposable external directories. Database writes, restores, replacements and
  cleanup require explicit scope and exact targets; verify targets and prefer
  recoverable operations.
- Put build products and bytecode outside the repository when practical. Never
  delete ignored caches or preserved review, smoke, backup, recovery or release
  evidence.

## Scope and documentation

- Implement only the requested slice, using the smallest architecture-consistent
  change. No speculative abstractions or unrelated features/refactoring.
  Without explicit scope, do not add UI changes, caching, background jobs,
  scheduling, comparison persistence, Marketplace features, new frameworks or
  premature performance optimization.
- Follow established architecture and explain conflicts with a requested design.
  Inspect nearby code/tests and conventions; do not assume planned paths match
  the repository's established layout.
- Update architecture documentation when establishing or changing a lasting
  rule. Record boundaries, lifecycle, failures, ordering, invariants, extension
  points and deliberate trade-offs. Avoid large duplicated sections and never
  describe speculative features as implemented.

## Testing and completion gates

- Every change includes focused behavior tests. Prefer application-service fakes,
  real SQLite repository/migration integration tests, deterministic clocks and
  fixtures, and explicit failure, immutability, ordering, corruption,
  transaction and rollback tests. Never weaken coverage to obtain a pass.
- Persistence coverage considers empty state, successful writes, multiple
  executions, equal timestamps, active outer transactions, savepoint rollback,
  foreign keys, serialization failure before mutation, malformed storage and
  fresh-schema/migration parity.
- Use focused checks while correcting. Before completing a candidate, always
  run the full test suite, compilation or type checks, `git diff --check`, and
  changed-content whitespace checks including new files. Inspect the complete
  final diff, exact scope and architecture boundaries; confirm no unrelated
  paths changed. Retain full final validation and CI at the publication gate.
- Disclose unavailable graphical tests as skips, never passes; manual GUI
  acceptance remains a separate human gate.
- Packaging/release changes require isolated artifact builds and installed
  artifact validation outside the checkout, using synthetic data and no real
  provider calls. Preserve existing build/release evidence.
- Report created/modified files, architecture/design decisions, lifecycle and
  transaction behavior, ordering/validation rules, tests/results, documentation
  changes, assumptions, trade-offs and remaining concerns. State whether the
  candidate is suitable for committing unchanged; this grants no authorization.

## Delivery discipline

- Protect dirty worktrees. Inspect branch, HEAD, index, tracked changes and
  untracked non-ignored paths before mutation; confirm scope and relevant docs.
- Use an isolated worktree unless the user explicitly authorizes implementation
  in an existing candidate worktree. Keep candidates uncommitted and unstaged
  until commit/push authorization is explicit. Never infer the next phase.
- Derive identities from Git; do not copy or guess hashes. Fail closed on
  identity, scope or validation drift.
- Obtain independent read-only review before PR publication and final
  committed-diff review before merge. Architecture, implementation, self-review,
  independent architectural review, focused correction and validation precede
  any separately authorized commit.
- Human approval is required for product/architecture choices, accepted scope,
  unresolved findings, manual GUI acceptance, commit/push, merge, version
  selection, tags/releases and destructive or meaningful database actions.
- Authorized commits remain focused, small enough to review and named for the
  capability delivered. Do not combine unrelated architecture, feature, UI and
  maintenance work or include unrelated formatting/cleanup.
- Never automatically merge, tag, publish, contact a real provider, access a
  personal database or remove preserved evidence.

## Code review rules

Prioritize consequential DIP risks: presentation calculations/queries/writes/
acquisition; mutable public models or contradictory typed states; eager providers
or construction/navigation/rendering side effects; schema/version/migration/
session/export/public-file incompatibility; incomplete ordering, provenance or
cross-result linkage; missing-versus-zero or Decimal reinterpretation; raw
exceptions, diagnostics, SQL, paths, tokens, provider payloads or personal data
entering user-facing/exported copy.

Passing tests alone is insufficient. Require architectural consistency,
determinism, understandability, maintainability, explicit failure behavior and
extension without unnecessary complexity. Report findings by severity with
precise evidence and the smallest safe fix. Approval only permits advancement
to the next separately authorized gate.
