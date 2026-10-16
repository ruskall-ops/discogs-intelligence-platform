# Personal-Use Release Checklist

## Release status and authority

DIP v0.7.0 is the current public personal-use release, released 2026-10-16.
DIP v0.6.0, released 2026-09-08, is the previous public release.
The historical v0.6.0 five-slice milestone remains complete and released.

This checklist records completed v0.7.0 gates, reusable accepted evidence and
the controlled publication procedure. Use a fresh artifact-clean checkout; do not remove
existing ignored builds, caches, or personal databases.

The procedure below does not authorise executing a repository or publication
operation. Commit, push, PR creation, merge, tag creation, artifact upload, and
GitHub release each remain subject to explicit authorisation. See the
[v0.7.0 release notes](../RELEASE_NOTES.md); the
[historical v0.6.0 notes](../RELEASE_NOTES.md#v060-release-notes) remain intact.

## v0.7.0 — publication verified

**Released 2026-10-16:** [DIP v0.7.0 — Current Collection Portfolio](https://github.com/ruskall-ops/discogs-intelligence-platform/releases/tag/v0.7.0).
Publication timestamp: `2026-10-16T10:45:33Z`; release ID `414846081`.
Source/runtime and distribution version are 0.7.0. The immutable release commit
is `5f525c3bb48b3dccc2015700441ff127fc3df22d`, tree
`365359357988b15d20d0d3763d498cb24ad97722`. This later housekeeping is a separate
change, not a replacement release source. Neither v0.7.0 nor historical tags or
assets may be moved or replaced by this documentation change.

The [release evidence matrix](../RELEASE_NOTES.md#release-evidence-matrix) separates
accepted Slice 3/PR #80 evidence from completed exact v0.7.0 candidate and
final-artifact checks. Prior CI, installed wheels and smoke remain supporting
evidence only, not substitutes for the final wheel/sdist validation. Deterministic geometry
recording does not establish native Configure-event delivery. Failure retention
used a launcher-only one-shot exception. Inconclusive lock attempts, incomplete
evidence-loss attempts and failed hosted native-resize checks retain their
original classifications.

Installed macOS gates and their applicability were resolved in the accepted
bounded campaign; no gate below is waived. Agent-operated synthetic verification
was accepted by the user without being relabelled human execution. The separate
authorized live-provider check was accepted with partial metadata and a one-run
Historical Intelligence skip, not complete-data or historical-comparison passes.
No blanket exception is approved for personal-data or provider testing.

Publication verification confirmed Latest, not draft/prerelease, the exact title
and approved body (newline normalization only), the annotated tag target and
exactly two uploaded assets with matching freshly downloaded hashes. The
remaining post-release work is this separately reviewed documentation-status
housekeeping; all prior evidence is preserved. No new build, test, provider,
repository or publication action is authorized merely by this checklist.

## Automated gates

- full unittest suite;
- source and test compilation;
- range-based whitespace validation;
- changed-document link validation;
- Linux and macOS GitHub Actions for the exact release candidate;
- mandatory production Tk on Linux/Xvfb and macOS/Aqua, exactly
  `run=7 pass=7 skip=0 error=0 failure=0`, without mandatory skips;
- fresh temporary database with migrations 1–7;
- genuine released-v0.4.0 upgrade through migrations 5–7;
- wheel and source-distribution installation;
- installed package, entry point, schema, and migration validation;
- database backup success and failure-safety coverage;
- fixed safe primary-workflow diagnostics;
- truthful enabled and disabled desktop controls.

## Manual macOS gates

Run these only when separately authorised, from the exact installed candidate.
Use disposable synthetic data by default. Any real personal Discogs run or
personal-database access requires explicit permission; a historical smoke does
not establish success for a newly versioned candidate. Unexecuted gates remain
pending, not passed.

- installed clean launch and fresh database;
- CSV import;
- controlled Collector Run and close blocking;
- Dashboard and Collector Review navigation;
- backup creation, verification, and overwrite;
- close, restart, and session restoration;
- disabled destination behavior;
- safe error presentation;
- disposable manual-recovery rehearsal;
- one controlled real personal Discogs run, only with separate permission;
- Project, Dashboard, Collection Review, Explorer Overview/Trends, Price
  Changes, and Supply Changes at `800×560`;
- legacy Markdown and Excel labels and unchanged analytical payloads.

## Release procedure — completed v0.7.0 record

The procedure and commands below document the completed v0.7.0 publication;
they are not instructions to tag, push, rebuild or publish v0.7.0 again.
Do not reuse them for an unapproved future release. The published source,
tag and assets remain immutable; this housekeeping is step 18.

The recorded release identifiers are documentation values, not shell variables:

| Identifier | Recorded v0.7.0 value |
|---|---|
| `RELEASE_VERSION` | `0.7.0` |
| `RELEASE_TAG` | `v0.7.0` |
| `RELEASE_BRANCH` | `chore/v0.7.0-release-preparation` |
| `RELEASE_TITLE` | `DIP v0.7.0 — Current Collection Portfolio` |
| `PREVIOUS_TAG` | `v0.6.0` |
| Base branch | `main` |

`PREVIOUS_TAG` is historical comparison context only. It is not the active tag
and must never be used by the active tag-creation, tag-push, or GitHub release
commands.

The completed publication followed this order, with separate authorisation for
each phase. Historically, preparation documentation remained draft/unreleased
until publication was verified. This post-release housekeeping records the
actual publication rather than inventing a date during preparation:

1. Prepare the draft, unreleased candidate wording on
   `chore/v0.7.0-release-preparation`.
2. Validate the complete candidate, including focused and full tests,
   compilation, links, artifacts, databases, upgrades, and generated-artifact
   checks.
3. Obtain independent read-only approval of the uncommitted preparation.
4. Commit the approved release preparation intentionally.
5. Push only the `chore/v0.7.0-release-preparation` branch with its upstream.
6. Open a pull request from `chore/v0.7.0-release-preparation` to `main`.
7. Require Linux and macOS CI to pass for the exact candidate, including
   mandatory Tk 7/7 with no skips, full discovery, compilation, artifacts,
   and whitespace validation.
8. Review and merge the pull request without rewriting history.
9. Fetch/prune and synchronize local `main` with `origin/main` using a
   fast-forward-only pull.
10. Verify that local `main` equals `origin/main`, contains the reviewed release
    commit, and has a clean working tree.
11. Rebuild and install the wheel and source distribution from clean, reviewed
    `main`; recheck version, metadata, entry point, packaged schema, migrations,
    Project reuse, provider laziness, and both User-Agent paths.
12. Perform the final installed macOS verification where required; do not
    substitute historical feature-commit smoke evidence.
13. Create the annotated `v0.7.0` tag from the reviewed commit on `main`.
14. Verify locally that `v0.7.0^{commit}` equals the reviewed `main` commit.
15. Push only the `v0.7.0` tag.
16. Create the GitHub release titled
    `DIP v0.7.0 — Current Collection Portfolio` from the verified `v0.7.0` tag.
17. Verify the GitHub release title, tag, target commit, Latest state, and notes;
    attach or publish artifacts only when explicitly approved.
18. Complete post-release documentation housekeeping in a separate reviewed
    change.

## Stop conditions

Stop immediately if:

- the working tree is dirty at a clean-tree gate;
- local `main` differs unexpectedly from `origin/main`;
- any Linux or macOS CI job fails;
- wheel or source-distribution validation fails;
- the required installed macOS smoke fails;
- `v0.7.0` already exists locally or remotely at an unexpected target;
- the proposed `v0.7.0` target is not the reviewed `main` commit;
- package or runtime version is not exactly `0.7.0`;
- migrations differ from exactly 1–7 or migration 8 exists;
- generated build, distribution, egg-info, wheel, source-distribution,
  bytecode, or cache artifacts remain;
- the reviewed commit is absent from `main`;
- any failure would require history rewriting or moving an existing release
  tag, including historical `v0.5.0`, `v0.5.1` and `v0.6.0`.

## Annotated tag and tag-only push

Run these commands only from clean, synchronized, reviewed `main`, after every
preceding gate passes:

```shell
git tag -a v0.7.0 -m "DIP v0.7.0 — Current Collection Portfolio"
git rev-parse HEAD
git rev-parse 'v0.7.0^{commit}'
git push origin v0.7.0
```

The two resolved commits must be identical before the tag push. The push command
must push only `v0.7.0`, never a branch or another tag.

## Manual GitHub website path

The manual website path is authoritative when GitHub CLI is unavailable:

1. Open the repository's **Releases** page and choose **Draft a new release**.
2. Select the existing verified tag `v0.7.0`; do not create or retarget a tag
   in the release form.
3. Confirm the selected tag targets the reviewed `main` commit.
4. Enter the title `DIP v0.7.0 — Current Collection Portfolio`.
5. Enter the reviewed release notes and mark the release **Latest**.
6. Do not attach artifacts unless that publication was explicitly approved.
7. Publish the release only after rechecking the title, tag, target, and notes.
8. Reopen the published release and verify its title, tag, target commit, Latest
   state, notes, and absence of unapproved artifacts.

## Optional GitHub CLI path

When `gh` is installed and authenticated, the optional equivalent path is:

```shell
gh release create v0.7.0 --verify-tag --latest --title "DIP v0.7.0 — Current Collection Portfolio" --notes-file APPROVED_V070_NOTES.md
gh release view v0.7.0
```

`APPROVED_V070_NOTES.md` denotes a separately approved external v0.7.0-only
publication-notes file, not an artifact created by this preparation. Preserve
the historical v0.6.0 section in `RELEASE_NOTES.md`; do not upload the combined
draft/historical document unchanged. Publication wording must be reviewed for
the actual authorized publication step. Do not
attach artifacts unless that publication is explicitly approved. No artifact
is published by the repository CI workflow.
