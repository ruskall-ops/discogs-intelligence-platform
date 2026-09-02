# Personal-Use Release Checklist

## Release status and authority

The current public release is **v0.6.0 — Results Presentation and UX
Refinement**, dated 2026-09-02. All five slices are complete and released.
v0.5.1 is the previous public release.

This checklist records the validated release scope and the controlled
publication procedure. Use a fresh artifact-clean checkout; do not remove
existing ignored builds, caches, or personal databases.

The procedure below does not authorise executing a repository or publication
operation. Commit, push, PR creation, merge, tag creation, artifact upload, and
GitHub release each remain subject to explicit authorisation. See the
[v0.6.0 release notes](../RELEASE_NOTES.md).

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

## Release procedure

The active release identifiers are declared as documentation values, not shell
variables:

| Identifier | Active value |
|---|---|
| `RELEASE_VERSION` | `0.6.0` |
| `RELEASE_TAG` | `v0.6.0` |
| `RELEASE_BRANCH` | `release/v0.6.0-publication-state` |
| `RELEASE_TITLE` | `DIP v0.6.0 — Results Presentation and UX Refinement` |
| `PREVIOUS_TAG` | `v0.5.1` |
| Base branch | `main` |

`PREVIOUS_TAG` is historical comparison context only. It is not the active tag
and must never be used by the active tag-creation, tag-push, or GitHub release
commands.

Only after each required authorisation, follow this exact release order:

1. Prepare the final publication-state wording on
   `release/v0.6.0-publication-state`.
2. Validate the complete candidate, including focused and full tests,
   compilation, links, artifacts, databases, upgrades, and generated-artifact
   checks.
3. Obtain independent read-only approval of the uncommitted preparation.
4. Commit the approved publication-state alignment intentionally.
5. Push only the `release/v0.6.0-publication-state` branch with its upstream.
6. Open a pull request from `release/v0.6.0-publication-state` to `main`.
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
13. Create the annotated `v0.6.0` tag from the reviewed commit on `main`.
14. Verify locally that `v0.6.0^{commit}` equals the reviewed `main` commit.
15. Push only the `v0.6.0` tag.
16. Create the GitHub release titled
    `DIP v0.6.0 — Results Presentation and UX Refinement` from the verified `v0.6.0` tag.
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
- `v0.6.0` already exists locally or remotely at an unexpected target;
- the proposed `v0.6.0` target is not the reviewed `main` commit;
- package or runtime version is not exactly `0.6.0`;
- migrations differ from exactly 1–7 or migration 8 exists;
- generated build, distribution, egg-info, wheel, source-distribution,
  bytecode, or cache artifacts remain;
- the reviewed commit is absent from `main`;
- any failure would require history rewriting or moving an existing release
  tag, including historical `v0.5.0` and `v0.5.1`.

## Annotated tag and tag-only push

Run these commands only from clean, synchronized, reviewed `main`, after every
preceding gate passes:

```shell
git tag -a v0.6.0 -m "DIP v0.6.0 — Results Presentation and UX Refinement"
git rev-parse HEAD
git rev-parse 'v0.6.0^{commit}'
git push origin v0.6.0
```

The two resolved commits must be identical before the tag push. The push command
must push only `v0.6.0`, never a branch or another tag.

## Manual GitHub website path

The manual website path is authoritative when GitHub CLI is unavailable:

1. Open the repository's **Releases** page and choose **Draft a new release**.
2. Select the existing verified tag `v0.6.0`; do not create or retarget a tag
   in the release form.
3. Confirm the selected tag targets the reviewed `main` commit.
4. Enter the title `DIP v0.6.0 — Results Presentation and UX Refinement`.
5. Enter the reviewed release notes and mark the release **Latest**.
6. Do not attach artifacts unless that publication was explicitly approved.
7. Publish the release only after rechecking the title, tag, target, and notes.
8. Reopen the published release and verify its title, tag, target commit, Latest
   state, notes, and absence of unapproved artifacts.

## Optional GitHub CLI path

When `gh` is installed and authenticated, the optional equivalent path is:

```shell
gh release create v0.6.0 --verify-tag --latest --title "DIP v0.6.0 — Results Presentation and UX Refinement" --notes-file RELEASE_NOTES.md
gh release view v0.6.0
```

Use an approved reviewed notes file in place of `RELEASE_NOTES.md`. Do not
attach artifacts unless that publication is explicitly approved. No artifact
is published by the repository CI workflow.
