---
name: dip-delivery
description: Run DIP planning, implementation, correction, review, PR publication, merge synchronization, or release gates while preserving explicit human authorization and machine-derived Git identity.
---

# DIP Delivery

Use this skill only for an explicitly requested DIP delivery mode: `plan`,
`implement`, `correct`, `review`, `publish-pr`, `merge-sync`, or `release`.

Before acting:

1. Read the repository `AGENTS.md`, required architecture documents, and the
   relevant approved specification or review findings.
2. Derive repository identity and candidate state with
   `python scripts/dip_delivery.py --mode <mode>`; add each authorized path with
   `--expected-path` when scope is closed.
3. Compare machine-derived identity with the user's authorization. Stop on
   drift, a failed gate, or a missing decision. Never parse decorative report
   prose as authoritative identity.
4. Read [references/modes.md](references/modes.md) for the selected mode only.

Implementation uses an isolated worktree and leaves the candidate uncommitted
and unstaged unless the user expressly authorizes publication. Prefer focused
checks during corrections; retain full final validation and CI gates.

Human authorization is always required for product/architecture decisions,
scope acceptance, unresolved findings, GUI acceptance, commit/push, merge,
version selection, tag/publication, and destructive or meaningful database
actions. Authorization for one phase never authorizes the next.

Never automatically merge, tag, release, contact a real provider, access a
personal database, or remove preserved evidence. Produce concise reports based
on structured tool output.
