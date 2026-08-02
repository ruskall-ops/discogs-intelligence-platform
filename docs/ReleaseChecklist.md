# Personal-Use Release Checklist

## Automated gates

- full unittest suite;
- source and test compilation;
- range-based whitespace validation;
- changed-document link validation;
- Linux and macOS GitHub Actions;
- fresh temporary database with migrations 1–7;
- genuine released-v0.4.0 upgrade through migrations 5–7;
- wheel and source-distribution installation;
- installed package, entry point, schema, and migration validation;
- database backup success and failure-safety coverage;
- fixed safe primary-workflow diagnostics;
- truthful enabled and disabled desktop controls.

## Manual macOS gates

- installed clean launch and fresh database;
- CSV import;
- controlled Collector Run and close blocking;
- Dashboard and Collector Review navigation;
- backup creation, verification, and overwrite;
- close, restart, and session restoration;
- disabled destination behavior;
- safe error presentation;
- disposable manual-recovery rehearsal;
- one controlled real personal Discogs run.

## Release procedure

The active release identifiers are declared as documentation values, not shell
variables:

| Identifier | Active value |
|---|---|
| `RELEASE_VERSION` | `0.5.1` |
| `RELEASE_TAG` | `v0.5.1` |
| `RELEASE_BRANCH` | `release/v0.5.1` |
| `RELEASE_TITLE` | `DIP v0.5.1 — Marketplace Change Explorer` |
| `PREVIOUS_TAG` | `v0.5.0` |
| Base branch | `main` |

`PREVIOUS_TAG` is historical comparison context only. It is not the active tag
and must never be used by the active tag-creation, tag-push, or GitHub release
commands.

For a prepared and validated release candidate, perform the release in this
exact order:

1. Prepare release changes on `release/v0.5.1`.
2. Validate the complete candidate, including focused and full tests,
   compilation, links, artifacts, databases, upgrades, and generated-artifact
   checks.
3. Obtain independent read-only approval of the uncommitted preparation.
4. Commit the approved release preparation intentionally.
5. Push only the `release/v0.5.1` branch with its upstream.
6. Open a pull request from `release/v0.5.1` to `main`.
7. Require Linux and macOS CI to pass.
8. Review and merge the pull request without rewriting history.
9. Fetch/prune and synchronize local `main` with `origin/main` using a
   fast-forward-only pull.
10. Verify that local `main` equals `origin/main`, contains the reviewed release
    commit, and has a clean working tree.
11. Rebuild and install the wheel and source distribution from clean, reviewed
    `main`; recheck version, metadata, entry point, packaged schema, migrations,
    Project reuse, provider laziness, and both User-Agent paths.
12. Perform the final installed macOS verification where required.
13. Create the annotated `v0.5.1` tag from the reviewed commit on `main`.
14. Verify locally that `v0.5.1^{commit}` equals the reviewed `main` commit.
15. Push only the `v0.5.1` tag.
16. Create the GitHub release titled
    `DIP v0.5.1 — Marketplace Change Explorer` from the verified `v0.5.1` tag.
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
- `v0.5.1` already exists locally or remotely at an unexpected target;
- the proposed `v0.5.1` target is not the reviewed `main` commit;
- package or runtime version is not exactly `0.5.1`;
- migrations differ from exactly 1–7 or migration 8 exists;
- generated build, distribution, egg-info, wheel, source-distribution,
  bytecode, or cache artifacts remain;
- the reviewed commit is absent from `main`;
- any failure would require history rewriting or moving an existing release
  tag, including historical `v0.5.0`.

## Annotated tag and tag-only push

Run these commands only from clean, synchronized, reviewed `main`, after every
preceding gate passes:

```shell
git tag -a v0.5.1 -m "DIP v0.5.1 — Marketplace Change Explorer"
git rev-parse HEAD
git rev-parse 'v0.5.1^{commit}'
git push origin v0.5.1
```

The two resolved commits must be identical before the tag push. The push command
must push only `v0.5.1`, never a branch or another tag.

## Manual GitHub website path

The manual website path is authoritative when GitHub CLI is unavailable:

1. Open the repository's **Releases** page and choose **Draft a new release**.
2. Select the existing verified tag `v0.5.1`; do not create or retarget a tag
   in the release form.
3. Confirm the selected tag targets the reviewed `main` commit.
4. Enter the title `DIP v0.5.1 — Marketplace Change Explorer`.
5. Enter the reviewed release notes and mark the release **Latest**.
6. Do not attach artifacts unless that publication was explicitly approved.
7. Publish the release only after rechecking the title, tag, target, and notes.
8. Reopen the published release and verify its title, tag, target commit, Latest
   state, notes, and absence of unapproved artifacts.

## Optional GitHub CLI path

When `gh` is installed and authenticated, the optional equivalent path is:

```shell
gh release create v0.5.1 --verify-tag --latest --title "DIP v0.5.1 — Marketplace Change Explorer" --notes-file RELEASE_NOTES.md
gh release view v0.5.1
```

Use an approved reviewed notes file in place of `RELEASE_NOTES.md`. Do not
attach artifacts unless that publication is explicitly approved. No artifact
is published by the repository CI workflow.
