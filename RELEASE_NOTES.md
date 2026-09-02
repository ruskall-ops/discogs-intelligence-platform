# DIP v0.6.0 — Results Presentation and UX Refinement

**Released 2026-09-02.**

The five-slice milestone is completed and released in v0.6.0. These final notes
describe the current public release. v0.5.1 is the previous public release.

## Release scope

The baseline is public tag `v0.5.1`, commit
`7141911b867cddd7a1031f4c8a8132df7194351a`. The complete release range includes:

- PR #65: documentation alignment with the completed v0.5.1 release.
- PR #66: canonical presentation states.
- PR #67: summary-first Price and Supply results.
- PR #68: Explorer navigation, explicit refresh, and stale-state presentation.
- PR #69: responsive Dashboard and Collection Review.
- PR #70: terminology, legacy report labels, and realistic-volume auditing.
- PR #71: version metadata, release documentation, release assertions, and
  exact-candidate release validation.

Release preparation adds only version metadata, release documentation, and
corresponding version/release assertions. It introduces no further product
feature or domain behavior. See [Changelog](CHANGELOG.md) for the change summary.

## What changes for the collector

Price and Supply Changes place comparison context and factual summaries before
detailed evidence, while preserving exact amounts, currencies, supply values,
deltas, classifications, and provenance. Current catalogue labels remain
distinct from captured snapshot evidence.

Explorer navigation retains full destination labels and truthful unavailable
states. Dashboard separates current collection facts from completed Collector
Run intelligence and available from unavailable destinations. Collection
Review improves table readability, detail sections, keyboard traversal, and
overflow at `800×560`.

Decision and Priority filters preserve exact retained stored values. Retained
filters restore as **All** after restart because session v1 stores canonical
filters only; stored decisions are not rewritten.

Legacy exports retain their filenames and analytical payloads:

- `discogs_intelligence_report.md`: **Legacy Collector Run analysis**.
- `Discogs_Intelligence_Export.xlsx`: **Legacy Collector Run review analysis**.

Their wants, scarcity, movers, rankings, and percentages are not Price Changes
2.0 or Supply Changes 2.0 results.

## Compatibility and limits

- Package/runtime version: `0.6.0`; database schema remains 7, with migrations
  exactly 1–7 and no migration 8.
- Price Changes and Supply Changes remain version 2.0. Listing Price Changes
  and Marketplace Activity remain version 1.0 without new production activation.
- No provider, persistence, session-format, dependency, or calculation change
  is introduced by release preparation. Existing User-Agent construction
  naturally follows the canonical application version.
- One practical Current Collection remains supported. Project partitioning,
  Marketplace Dashboard, listing acquisition, automatic refresh, and automated
  decisions remain outside this release scope.
- macOS remains the primary personal-use platform; Linux receives automated
  compatibility validation. Windows is unsupported. Keyboard and layout
  validation is not screen-reader certification.

## Validation evidence and publication boundary

The exact PR #71 candidate passed Linux/Xvfb and macOS/Aqua CI, including the
mandatory production-Tk suite with `run=7 pass=7 skip=0 error=0 failure=0`,
full discovery, compilation, isolated artifact validation, and whitespace
validation. Its installed-wheel macOS smoke passed presentation, CSV import,
controlled Collector Run, backup and replacement, session restoration,
verified-backup recovery, and safe worker-start error handling using synthetic
data with real provider/network access blocked.

The publication-state alignment changes only release-facing documentation and
the assertions that protect that wording. It introduces no product behavior.
Final artifacts are built and validated from the exact tagged tree.

Follow the [release checklist](docs/ReleaseChecklist.md), including fresh and
genuine released-v0.4.0 upgrade validation. Any personal-data or real-provider
manual gate requires separate explicit permission and must not run as part of
this preparation. Preserve existing databases and ignored artifacts; use an
artifact-clean checkout and disposable synthetic fixtures.

The release process uses separately authorised, reviewed commit, tag, artifact,
and GitHub publication steps; no provider or personal-data access is part of
that process.
