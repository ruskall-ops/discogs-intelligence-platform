# DIP v0.7.0 — Current Collection Portfolio

**Released 2026-10-16.** [Published GitHub release](https://github.com/ruskall-ops/discogs-intelligence-platform/releases/tag/v0.7.0),
publication timestamp `2026-10-16T10:45:33Z`; release ID `414846081`.
v0.6.0, released 2026-09-08, is the previous public release.

The immutable release source is commit
`5f525c3bb48b3dccc2015700441ff127fc3df22d`, tree
`365359357988b15d20d0d3763d498cb24ad97722`, annotated tag `v0.7.0`
(`a33eb465541d99c48344f5f537f61cb307d68f89`). This later documentation-status
housekeeping does not move the tag, change published assets, or identify a new
release artifact. Its eventual commit/tree are distinct from that release source.

## Release scope

The accepted implementation baseline is merged main
`3fb66b5b08027f0f89eb10094341a2ad5da94097`, tree
`4e196c93e041d11f1fcb3ed3755307eddce31fef`. The published comparison baseline is
v0.6.0, commit `69e84b7a2b0eed56a5729dd77ccc4cc96d00b729`.
The accepted changes include PRs #74–#75 and #77–#80 for Portfolio execution,
presentation, desktop activation, Dashboard startup, SQLite-row integration
and session fallback; PR #76 provides engineering delivery automation.
The release preparation added only version metadata, release documentation and
their validation expectations. This post-publication housekeeping changes only
documentation status and corresponding assertions, not product functionality.

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

Runtime/distribution version is `0.7.0`; schema remains 7, migrations exactly 1–7
and no migration 8, session format 1. Dependencies, calculation/Decimal values,
module versions, ordering, ownership, history, exports and provider/persistence
contracts are unchanged. Existing User-Agent construction follows the canonical
runtime version. One Current Collection remains supported. Project partitioning,
Portfolio Overview/Opportunity Alignment/History/Research, listing acquisition,
Marketplace activation, automatic refresh and automated decisions remain deferred.
macOS remains primary, Linux receives automated compatibility validation,
and Windows remains unsupported. No screen-reader certification is claimed.

## Release evidence matrix

| Gate | Evidence and acceptance classification | v0.7.0 release status |
|---|---|---|
| Portfolio behavior | Accepted Slice 3 human observations and scripted real-Tk verification; exact final-wheel synthetic campaign operated by the agent and accepted by the user | Complete within the agreed bounded plan; agent operations are not human execution |
| Session geometry | PR #80 real-Tk small-window lifecycle cases and deterministic complete-tuple recording; final-wheel close/restart and non-default restoration | Complete with the native-event limitation below |
| Exact-candidate CI | PR #81 head `1afd5767581119ebcc43da68a8502992f6ef22e8`, same tree as the immutable release source; [run 38369409742](https://github.com/ruskall-ops/discogs-intelligence-platform/actions/runs/38369409742) | Linux/macOS passed; this is PR-head CI, not a claimed merge-SHA CI run |
| Source validation | 1,212 discovered; 1,211 source tests executed and passed, zero skips/errors/failures; installed-distribution test excluded at that stage | Separate from the four later installed tests; not one combined local full-suite run |
| Final-main wheel and sdist | Isolated builds, unmodified artifact validator, installed-only origins, runtime/distribution 0.7.0, entry point, packaged schema and both User-Agent paths; four installed tests passed separately | Complete; final published hashes below |
| Compatibility | Fresh databases and genuine released-v0.4.0 upgrades; integrity/quick checks, foreign keys, migrations exactly 1–7 and session format 1 | Complete; no migration 8 or format change |
| Installed macOS | Exact-wheel navigation/sizing, CSV stale/refresh bridge, synthetic Collector Run/close blocking, exports, backup/approved overwrite, separate-copy recovery and session restoration | Agent-operated, including documented programmatic Tk controls; accepted by the user, distinct from earlier human observations |
| Safe diagnostics | Launcher-only one-shot repository failure retention and backup-validation exception; subsequent normal operations and unchanged-data audits | Accepted injected-error coverage, not naturally occurring database/provider faults |
| Bounded real provider | One user-owned release, one authorized GUI run, one provider construction/GET, HTTP 200; user-only masked token entry, agent operation, normal close and expected writes | Accepted partial live snapshot; Historical Intelligence skipped with only one run, not a historical-comparison pass |
| Publication | Published release ID 414846081; Latest, not draft/prerelease; approved body matches after newline normalization; exactly two uploaded assets freshly downloaded and hashed | Verified 2026-10-16; generated GitHub source archives are not uploaded assets |

Exact-candidate CI mandatory Tk was `run=7 pass=7 skip=0 error=0 failure=0`
on both platforms. Linux full discovery ran 1,212: 1,210 passed and two
case-insensitive-filesystem tests skipped. macOS ran and passed 1,212 with zero
skips; neither platform had errors or failures. Compilation, artifact validation
and changed-content whitespace passed on both. PR #80 and historical v0.6.0
validation remain supporting evidence, not substitutes for these exact-tree and
final-artifact checks. Detailed private evidence remains outside the repository.

Deterministic geometry recording does not establish native Configure-event
delivery. Earlier successful local native resizing remains supporting evidence;
earlier hosted failures remain failures. Failure retention was induced through
a launcher-only one-shot repository exception. SQLite-lock attempts remain
inconclusive; the evidence-loss attempt remains incomplete with final database
state unverifiable. Agent-operated real-Tk traversal is not labelled a human pass.

The bounded live snapshot was partial because lowest-price currency was missing;
currency was not inferred. Historical Intelligence skipped because only one run
was available. These outcomes are not complete-data or historical-comparison
passes. The one-request check does not establish full-collection integration,
retry/backoff or provider-fault recovery. Synthetic orchestration remains
distinct from this authorized live-provider execution.

The user accepted the bounded synthetic and live evidence with these limitations;
no checklist gate was silently waived. Additional personal-data/provider work
still requires explicit authorization. See the
[release checklist](docs/ReleaseChecklist.md) for the completed procedure and
continuing safeguards.

## Verified published assets

| Uploaded asset | Bytes | SHA-256 |
|---|---:|---|
| `discogs_intelligence_platform-0.7.0-py3-none-any.whl` | 535420 | `5a35d7485ffb6bb34f0b7e5048f4344fdc3ac313591cc4a5f89827d048f1c5ba` |
| `discogs_intelligence_platform-0.7.0.tar.gz` | 667159 | `685dcef2b796dd9f83276179aadf6c073fc82ed365fe7fe2c05cf7d1e7685256` |

## Historical release notes

The following v0.6.0 notes retain their publication-time wording and facts.
References to the current/previous release within that historical section refer
to its 2026-09-08 publication, not the current v0.7.0 status.

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
