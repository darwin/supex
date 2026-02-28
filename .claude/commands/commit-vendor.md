---
name: commit-vendor
description: Commit vendored submodule pointer changes (push patches + commit)
---

Commit updated vendored submodule pointers in the supex repo. This command handles ONLY the commit step — fetching, rebasing, and testing are done by `review-vendor`.

All paths below are relative to the supex repo root.

### Submodule types

There are two kinds of vendored submodules:

- **Patch repos** (`vcad/vendor/loon`, `vcad/vendor/vcad`) — have a darwin fork with a `supex-patches` branch that carries local patches rebased on top of upstream `origin/main`.
- **Plain repos** (`vcad/vendor/phyz`, `vcad/vendor/tang`) — track upstream `origin/main` directly, no fork, no patches.

## Step 1: Detect changed pointers

Check which submodules have changed pointers relative to the last supex commit:
```
git diff --submodule=short -- vcad/vendor/
git diff --cached --submodule=short -- vcad/vendor/
```

If no submodule pointers changed, report "nothing to commit" and stop.

## Step 2: Compute upstream ranges

For each submodule with a changed pointer, compute the upstream commit range for the commit message.

### Get pointer SHAs

```bash
# SHA stored in supex repo (last commit)
old_pointer=$(git rev-parse HEAD:vcad/vendor/<name>)
# SHA currently in worktree (after rebase(s) from review-vendor)
new_pointer=$(git -C vcad/vendor/<name> rev-parse HEAD)
```

### Resolve to upstream commits

**Plain repos (tang):** The pointer IS the upstream commit directly.
```bash
old_upstream=$old_pointer
new_upstream=$new_pointer
```

**Patch repos (loon, vcad):** The pointer is on `supex-patches` (rebased). Use merge-base with `origin/main` to find the upstream base.
```bash
old_upstream=$(git -C vcad/vendor/<name> merge-base $old_pointer origin/main)
new_upstream=$(git -C vcad/vendor/<name> merge-base $new_pointer origin/main)
```

This works correctly even after multiple review-vendor cycles — merge-base always finds the upstream base of a rebased commit.

### Validate

If `old_upstream` == `new_upstream` for a submodule, that means no new upstream commits were incorporated (only local patch changes). Still commit the pointer update, but use a different message:
```
Update <name> vendor supex-patches
```

## Step 3: Show summary

Before pushing or committing, display a summary to the user:

For each changed submodule:
- Repo name
- Old upstream → new upstream (short SHAs)
- GitHub compare link: `https://github.com/ecto/<name>/compare/<old_upstream>...<new_upstream>`
- Number of new upstream commits (if any)

Ask the user to confirm before proceeding.

## Step 4: Push patch repos

Push ALL changed **patch repos** to GitHub before any commits:
```
git -C vcad/vendor/<name> push darwin supex-patches
```

Plain repos (phyz, tang) don't need pushing — they point directly at upstream commits which are already public.

If any push fails, STOP and report the error — do NOT commit any pointers. If some pushes succeed and others fail, report partial state and let user decide.

## Step 5: Commit

After all pushes succeed, create a **separate commit** for each changed submodule:

```
git add vcad/vendor/<name>
git commit -m "Roll <name> vendor on top of <old_upstream>..<new_upstream>

https://github.com/ecto/<name>/compare/<old_upstream>...<new_upstream>"
```

If the submodule had no new upstream commits (only patch changes), use:
```
git add vcad/vendor/<name>
git commit -m "Update <name> vendor supex-patches"
```

Only stage one submodule pointer per commit — never bundle multiple submodules or other files.

### Important

- Push MUST succeed before committing — a commit with unreachable submodule pointers breaks `git clone --recurse-submodules`
- Process submodules in order: tang, loon, phyz, vcad
- This command may run after multiple review-vendor cycles — the range computation handles this correctly via merge-base
