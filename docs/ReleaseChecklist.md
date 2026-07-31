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

For a prepared and validated release candidate, perform the release in this
exact order:

1. prepare release changes on `release/v0.5.0`;
2. complete the read-only review;
3. correct all findings;
4. commit intentionally;
5. push the release branch;
6. create a pull request to `main`;
7. require Linux and macOS CI to pass;
8. review and merge the pull request;
9. fetch/prune and synchronize local `main` with `origin/main`;
10. confirm the reviewed release commit is on `main`;
11. rebuild the wheel and source distribution from clean, merged `main`;
12. install each artifact in an isolated environment;
13. rerun version, metadata, entry-point, schema, migration, Project reuse,
    provider-laziness, and both User-Agent validations;
14. perform the final installed macOS smoke;
15. confirm the working tree is clean, package/runtime versions are exactly
    0.5.0, migrations are exactly 1–7, and `v0.4.0` is unchanged;
16. create an annotated `v0.5.0` tag from the reviewed commit on `main`;
17. verify the tag target locally;
18. push only the `v0.5.0` tag;
19. create the GitHub release from that tag;
20. attach or publish artifacts only when explicitly approved;
21. verify the resulting release metadata.

Stop immediately for any failing test or CI job, dirty working tree, version
mismatch, migration or schema change, artifact-validation failure, macOS smoke
failure, tag already existing at an unexpected target, reviewed commit absent
from `main`, local `main` differing from `origin/main`, accidental generated
artifacts, or any failure that would require history rewriting or moving
`v0.4.0`.

The GitHub release may be created manually on the GitHub website by selecting
the verified `v0.5.0` tag, entering the reviewed release title and notes, and
publishing only after checking the target and metadata. This path requires no
GitHub CLI.

When `gh` is installed and authenticated, the optional CLI path is:

```shell
gh release create v0.5.0 --verify-tag --title "Version 0.5.0 — Collector Workflow Foundation" --notes-file RELEASE_NOTES.md
gh release view v0.5.0
```

Use an approved reviewed notes file in place of `RELEASE_NOTES.md`. Do not
attach artifacts unless that publication is explicitly approved.

No artifact is published by the repository CI workflow.
