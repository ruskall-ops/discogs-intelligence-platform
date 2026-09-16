# Delivery Modes

Read only the section for the requested mode.

## plan

Verify the baseline and evidence, distinguish confirmed facts from proposals,
and write specifications outside the repository. Stop for scope acceptance.

## implement

Create an isolated worktree from the approved base. Implement only the accepted
slice, run focused validation, and leave an uncommitted, unstaged candidate for
independent review.

## correct

Work in the named candidate worktree. Apply only approved findings, preserve
already accepted boundaries, run proportionate focused checks, and return the
candidate unstaged for another review.

## review

Remain strictly read-only. Verify identities, inspect the complete relevant
diff and public boundaries, run proportionate checks externally, and return
`APPROVED`, `CHANGES REQUIRED`, or `BLOCKED`. Approval grants no mutation.

## publish-pr

Require explicit commit/push authorization and an approved candidate identity.
Reproduce its tree without changing the index, stage only approved paths,
commit normally, push only the feature branch, and open a non-draft PR when
authenticated tooling is available. Stop with the PR open and unmerged.

## merge-sync

Require explicit merge authorization and successful exact-head CI/review.
Recheck the PR head immediately before a normal merge, synchronize local main
with `--ff-only`, verify ancestry and clean state, and delete only explicitly
authorized merged branches.

## release

Treat version selection, artifact construction, installed-wheel smoke, tag
creation, tag push, GitHub release creation, upload, and publication as distinct
gates. Use exact committed source and verified artifacts. Perform only the gates
explicitly authorized in the current request.
