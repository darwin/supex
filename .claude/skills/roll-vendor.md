# Roll vendor

Trigger: user says "roll vendor", "roll deps", "update vendor", "rebase vendor"

## What this does

Rebases `supex-patches` branches in vendored submodules (loon, phyz, vcad) on top of latest upstream changes.

## Steps

For each submodule in `vcad/vendor/loon`, `vcad/vendor/phyz`, `vcad/vendor/vcad`:

1. Fetch from upstream: `git -C <submodule> fetch origin`
2. Ensure we're on `supex-patches`: `git -C <submodule> checkout supex-patches`
3. Rebase onto upstream main: `git -C <submodule> rebase origin/main`

All paths are relative to the supex repo root.

## Important

- Run repos sequentially, not in parallel — user needs to see progress and handle conflicts
- If rebase fails with conflicts, STOP and report which repo has conflicts — do NOT abort the rebase automatically
- Proactively assist with conflict resolution: show the conflicting files, read them, explain what both sides changed, and suggest a resolution — but always let the user confirm before proceeding
- Report summary at the end: which repos were rebased successfully, how many new commits were pulled in
- After successful rebase, remind user to rebuild all projects that depend on vendored libraries (sidecar, viewer, etc.)
