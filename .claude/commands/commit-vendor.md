---
name: commit-vendor
description: Commit vendored submodule pointer changes (push patches + commit)
---

Commit updated vendored submodule pointers in the supex repo. This command handles ONLY the commit step — fetching, rebasing, and testing are done by `review-vendor`.

All paths below are relative to the supex repo root.

### Submodule types

There are two kinds of vendored submodules:

- **Patch repos** (`vcad/vendor/loon`, `vcad/vendor/vcad`) — have a darwin fork with a `supex-patches` branch that carries local patches rebased on top of upstream `origin/main`.
- **Plain repos** (`vcad/vendor/tang`) — track upstream `origin/main` directly, no fork, no patches.

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

## Step 4: Archive + push patch repos

For each changed **patch repo**, archive the old state and push the new one. Plain repos (tang) don't need pushing — they point directly at upstream commits which are already public.

### Archive old supex-patches

Before force-pushing, tag the current remote HEAD so old submodule pointers remain reachable (prevents GC of commits referenced by older supex commits):

```bash
old_head=$(git -C vcad/vendor/<name> rev-parse darwin/supex-patches)
short=$(echo $old_head | head -c 8)
git -C vcad/vendor/<name> tag "archive/$short" $old_head
git -C vcad/vendor/<name> push darwin "archive/$short"
```

If the tag already exists (idempotent re-run), skip it.

### Push new supex-patches

```bash
git -C vcad/vendor/<name> push darwin supex-patches
```

If any push fails, STOP and report the error — do NOT commit any pointers. If some pushes succeed and others fail, report partial state and let user decide.

## Step 5: Commit

After all pushes succeed, create a **single atomic commit** with all changed submodule pointers and any modified build artifacts.

### Stage all changes

```bash
# Stage all changed submodule pointers
git add vcad/vendor/tang vcad/vendor/loon vcad/vendor/vcad  # only those that changed

# Stage Cargo.lock if modified by the rebuild
git diff --quiet -- vcad/sidecar/Cargo.lock || git add vcad/sidecar/Cargo.lock
```

### Commit message format

**Subject line:** Use `ecto/<name>@<new_upstream_short>` autolinks (clickable on GitHub). For submodules with only patch changes (no new upstream), use just the name without `@sha`.

**Body:** Full GitHub compare URLs for each submodule that has new upstream commits (omit for patch-only changes).

Example with upstream rolls:
```
Roll vendor: ecto/tang@6aeba2b, ecto/loon@256fa95, ecto/vcad@1b59e79

https://github.com/ecto/tang/compare/<old_upstream>...<new_upstream>
https://github.com/ecto/loon/compare/<old_upstream>...<new_upstream>
https://github.com/ecto/vcad/compare/<old_upstream>...<new_upstream>
```

If ALL submodules are patch-only (no new upstream), use "Update vendor" instead of "Roll vendor" in the subject.

### Important

- Push MUST succeed before committing — a commit with unreachable submodule pointers breaks `git clone --recurse-submodules`
- Process submodules in order: tang, loon, vcad
- This command may run after multiple review-vendor cycles — the range computation handles this correctly via merge-base
