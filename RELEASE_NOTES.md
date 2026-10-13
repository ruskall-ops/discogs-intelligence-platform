# DIP v0.7.0 — Current Collection Portfolio

**Draft — unreleased.** v0.6.0 remains the current public personal-use release,
released 2026-09-08. No v0.7.0 release date, tag or publication is claimed.

## Proposed release scope

The accepted implementation baseline is merged main
`3fb66b5b08027f0f89eb10094341a2ad5da94097`, tree
`4e196c93e041d11f1fcb3ed3755307eddce31fef`. The published comparison baseline is
v0.6.0, commit `69e84b7a2b0eed56a5729dd77ccc4cc96d00b729`.
The accepted changes include PRs #74–#75 and #77–#80 for Portfolio execution,
presentation, desktop activation, Dashboard startup, SQLite-row integration
and session fallback; PR #76 provides engineering delivery automation.
This preparation adds only version metadata, release documentation and their
validation expectations. It adds no new product functionality.

## Current Collection Portfolio

Toolbar and Dashboard open one shared window with Distribution and
Concentration only. Distribution preserves release/copy totals, metadata
coverage, missing identities, ordered categories, evidence and provenance.
Concentration uses the exact linked Distribution result and represented-membership
denominators with full-collection coverage alongside them. It describes
mathematical clustering, not recommendations, valuation or an aggregate score.

One execution occurs on new open or explicit refresh. Focus, navigation and
scrolling do not execute. A committed CSV import marks an open result out of
date before display refresh; failed or cancelled import does not. Refresh
failure retains the displayed pair and previous freshness. Active Collector Run
blocks Portfolio open/refresh. Viewing makes no provider call, history record
or database write. Portfolio results remain transient and are not session-restored.

## Small-window session fallback

The root and Portfolio child retain separate `800×560` minimums. Configuration
still accepts width 800 and height 500; Tk enforces root height 560. Startup
initializes session-valid fallback dimensions through the existing sanitizer.
Session format 1 requires at least `1050×650`; only later valid normal geometry
replaces that fallback. Undersized resizing preserves the full last-valid tuple.
A normal close saves valid session geometry, and restart restores that geometry,
not necessarily the smaller visible size. Stored-record validation is unchanged.

## Compatibility and deferred scope

Runtime/distribution target `0.7.0`; schema remains 7, migrations exactly 1–7
and no migration 8, session format 1. Dependencies, calculation/Decimal values,
module versions, ordering, ownership, history, exports and provider/persistence
contracts are unchanged. Existing User-Agent construction follows the canonical
runtime version. One Current Collection remains supported. Project partitioning,
Portfolio Overview/Opportunity Alignment/History/Research, listing acquisition,
Marketplace activation, automatic refresh and automated decisions remain deferred.
macOS remains primary, Linux receives automated compatibility validation,
and Windows remains unsupported. No screen-reader certification is claimed.

## Release evidence matrix

| Gate | Reusable evidence | v0.7.0 release status |
|---|---|---|
| Portfolio behavior | Accepted Slice 3 reviews and bounded human/scripted smoke | Acceptance retained; installed candidate check pending |
| Session geometry | PR #80 review; two real-Tk lifecycle cases and deterministic recording | Accepted behavior; new candidate validation required |
| CI | PR #80 run [38264318729](https://github.com/ruskall-ops/discogs-intelligence-platform/actions/runs/38264318729), Linux/macOS passed | Exact preparation-head CI pending |
| Source checks | Matching prior tests/compilation/whitespace | New candidate source validation required; measured results belong in external evidence |
| Wheel and sdist | Prior v0.6.0 checks | New isolated builds, hashes, installs and provenance validation pending |
| Compatibility | Fresh schema and genuine v0.4 upgrade coverage | Exact candidate checks required; migrations 1–7 unchanged |
| Installed GUI | Accepted synthetic Portfolio/import/close evidence | Exact v0.7.0 installed macOS gates and applicability review pending |
| Publication | Published v0.6.0 history | Review, commit/push/merge, final artifacts, tag and publication separately authorized |

The PR #80 CI evidence has mandatory Tk 7/7 with zero skips on both platforms;
full discovery passed 1,210 on macOS and 1,208 with two case-insensitive-filesystem
skips on Linux. It is supporting evidence, not exact v0.7.0 preparation CI.
Deterministic geometry recording does not establish native Configure-event
delivery. Earlier successful local native resizing remains supporting evidence;
earlier hosted failures remain failures. Failure retention was induced through
a launcher-only one-shot repository exception. SQLite-lock attempts remain
inconclusive; the evidence-loss attempt remains incomplete with final database
state unverifiable. Agent-operated real-Tk traversal is not labelled a human pass.

Broader GUI/checklist applicability remains pending. No exception is approved
for personal-data or provider testing. See the [release checklist](docs/ReleaseChecklist.md).
Builds, installed GUI smoke, commit, push, PR, merge, tags and publication each
require separate authorization. Do not reuse old artifacts as v0.7.0 proof.

<a id="v060-release-notes"></a>

## DIP v0.6.0 — Results Presentation and UX Refinement

**Released 2026-09-08.**

The five-slice milestone is completed and released in v0.6.0. These final notes
describe the current public release. v0.5.1 is the previous public release.

### Release scope

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

### What changes for the collector

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

### Compatibility and limits

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

### Validation evidence and publication boundary

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
