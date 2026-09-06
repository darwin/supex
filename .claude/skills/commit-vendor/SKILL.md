---
name: commit-vendor
description: Commit vendored submodule pointer changes
---

Commit updated vendored submodule pointers in the supex repo. This command handles ONLY the commit step — fetching, reviewing, and testing are done by `review-vendor`.

All paths below are relative to the supex repo root.

### Submodules

All vendored submodules (`vcad/vendor/tang`, `vcad/vendor/loon`, `vcad/vendor/vcad`) track upstream `origin/main` directly — no fork, no local patches. A pointer is always an upstream commit, so nothing has to be pushed before committing.

## Step 1: Detect changed pointers

Check which submodules have changed pointers relative to the last supex commit:
```
git diff --submodule=short -- vcad/vendor/
git diff --cached --submodule=short -- vcad/vendor/
```

If no submodule pointers changed, report "nothing to commit" and stop.

## Step 2: Compute upstream ranges

For each submodule with a changed pointer:

```bash
# SHA stored in supex repo (last commit)
old_upstream=$(git rev-parse HEAD:vcad/vendor/<name>)
# SHA currently in worktree
new_upstream=$(git -C vcad/vendor/<name> rev-parse HEAD)
```

### Validate reachability

The new pointer MUST be reachable from the upstream remote, otherwise `git clone --recurse-submodules` breaks:

```bash
git -C vcad/vendor/<name> branch -r --contains $new_upstream | grep -q origin/ || echo "NOT ON UPSTREAM"
```

If a pointer is not on upstream (e.g. a local experiment), STOP and report — do not commit it.

## Step 3: Show summary

Before committing, display a summary to the user:

For each changed submodule:
- Repo name
- Old upstream → new upstream (short SHAs)
- GitHub compare link: `https://github.com/ecto/<name>/compare/<old_upstream>...<new_upstream>`
- Number of new upstream commits: `git -C vcad/vendor/<name> rev-list --count $old_upstream..$new_upstream` (a rollback shows 0 — say so)

Ask the user to confirm before proceeding.

## Step 4: Commit

Create a **single atomic commit** with all changed submodule pointers and any modified build artifacts.

### Stage all changes

```bash
# Stage all changed submodule pointers
git add vcad/vendor/tang vcad/vendor/loon vcad/vendor/vcad  # only those that changed

# Stage Cargo.lock if modified by the rebuild
git diff --quiet -- vcad/sidecar/Cargo.lock || git add vcad/sidecar/Cargo.lock
```

### Commit message format

**Subject line:** Use `ecto/<name>@<new_upstream_short>` autolinks (clickable on GitHub).

**Body:** Full GitHub compare URLs for each submodule.

Example:
```
Roll vendor: ecto/tang@6aeba2b, ecto/loon@256fa95, ecto/vcad@1b59e79

https://github.com/ecto/tang/compare/<old_upstream>...<new_upstream>
https://github.com/ecto/loon/compare/<old_upstream>...<new_upstream>
https://github.com/ecto/vcad/compare/<old_upstream>...<new_upstream>
```

### Important

- Process submodules in order: tang, loon, vcad
- Never commit a pointer that is not reachable from upstream
