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

The implemented v0.5.6 milestone remains package/runtime version 0.4.0 and
creates no tag. Only after every automated and manual gate passes may a
separate reviewed release change:

1. update package and runtime version to 0.5.0;
2. confirm both Discogs User-Agents inherit the runtime version;
3. add release notes;
4. rebuild and reinstall wheel and source distribution;
5. rerun automated and manual validation;
6. create the reviewed `v0.5.0` tag.

No artifact is published by the repository CI workflow.
