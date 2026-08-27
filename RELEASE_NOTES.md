# DIP v0.6.0 — Results Presentation and UX Refinement

**Draft — unreleased; release preparation only.**

The five-slice milestone is accepted. These notes do not assert a published
release, completed release-candidate CI, or a new release-candidate macOS smoke.
v0.5.1 remains the latest completed public release. No release date is assigned.

## Release scope

The baseline is public tag `v0.5.1`, commit
`7141911b867cddd7a1031f4c8a8132df7194351a`. The accepted implementation ends at
merged main commit `4acd518488d187657c3c652236f06309ed56fdb6` and includes:

- PR #65: documentation alignment with the completed v0.5.1 release.
- PR #66: canonical presentation states.
- PR #67: summary-first Price and Supply results.
- PR #68: Explorer navigation, explicit refresh, and stale-state presentation.
- PR #69: responsive Dashboard and Collection Review.
- PR #70: terminology, legacy report labels, and realistic-volume auditing.

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

- Package/runtime candidate: `0.6.0`; database schema remains 7, with migrations
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

## Evidence and outstanding gates

The accepted milestone has historical feature-commit Linux/macOS CI and an
installed-wheel macOS visual smoke. These are not evidence that this new
`0.6.0` candidate has passed its own release gates.

Before publication, require independent review of the exact preparation diff,
full automated and artifact validation, mandatory Tk `run=7 pass=7 skip=0
error=0 failure=0` on Linux/Xvfb and macOS/Aqua for the exact candidate, and
the required exact-candidate installed-wheel macOS smoke. Record actual results
separately; do not mark unexecuted gates complete.

Follow the [release checklist](docs/ReleaseChecklist.md), including fresh and
genuine released-v0.4.0 upgrade validation. Any personal-data or real-provider
manual gate requires separate explicit permission and must not run as part of
this preparation. Preserve existing databases and ignored artifacts; use an
artifact-clean checkout and disposable synthetic fixtures.

Commit, push, PR creation, merge, tagging, and publication require their next
explicit authorisation. No release artifact upload is authorised by this draft.
