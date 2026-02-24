---
name: roll-vendor
description: Rebase vendored submodules on upstream and optionally commit
---

Rebase `supex-patches` branches in vendored submodules (loon, phyz, vcad) on top of latest upstream changes, then offer follow-up actions.

All paths below are relative to the supex repo root.

## Phase 1: Roll (rebase)

For each submodule in `vcad/vendor/loon`, `vcad/vendor/phyz`, `vcad/vendor/vcad`:

1. Record the current upstream base before fetch: `git -C <sub> rev-parse origin/main` → save as `<old-upstream>`
2. Fetch from both remotes: `git -C <sub> fetch origin && git -C <sub> fetch darwin`
3. Record the new upstream head: `git -C <sub> rev-parse origin/main` → save as `<new-upstream>`
4. If `<old-upstream>` == `<new-upstream>`, report "no new upstream commits" and skip to the next submodule
5. Check for dirty state (see below)
6. Check current branch — may be `supex-patches` or detached HEAD
7. If detached HEAD: restore `supex-patches` from darwin fork: `git -C <sub> checkout -B supex-patches darwin/supex-patches`
8. Rebase `supex-patches` onto upstream main: `git -C <sub> rebase origin/main`
9. Show new upstream commits summary (`<old-upstream>..<new-upstream>`)

Save the `<old-upstream>` and `<new-upstream>` pair for each rolled submodule — these are needed in Phase 3 for commit messages.

### Dirty worktree handling

Vendor repos may appear clean in `git status` but have hidden local changes due to `assume-unchanged` flags or `.gitmodules` `ignore = dirty` settings. This is intentional — we pin Cargo.lock locally.

**Before rebasing each repo:**
1. Run `git -C <sub> ls-files -v | grep ^h` to detect assume-unchanged files
2. If any found, **STOP and tell the user** — explain which files have the flag and that they need to be resolved before rebase can proceed
3. Typical resolution: `git update-index --no-assume-unchanged <file>` then `git checkout -- <file>` or `git stash`
4. Let the user decide how to handle it — do NOT automatically reset or stash

### Important

- Run repos sequentially, not in parallel — user needs to see progress and handle conflicts
- If rebase fails with conflicts, STOP and report which repo has conflicts — do NOT abort the rebase automatically
- Proactively assist with conflict resolution: show the conflicting files, read them, explain what both sides changed, and suggest a resolution — but always let the user confirm before proceeding

## Phase 2: After rolling

Report summary: which repos were rolled, how many new commits were pulled in, which had no changes.

Automatically run rebuild and tests:

1. **Rebuild**: `./scripts/rebuild.sh` to rebuild all binaries (sidecar + viewer)
2. **Test**: `./test` to run all headless tests

If rebuild fails, STOP and report the error — do not run tests.
If tests fail, report failures but continue to the commit prompt.

After rebuild and tests, **ask the user** whether to commit vendor (push `supex-patches` branches and commit submodule pointers — see below).

## Phase 3: Commit vendor (when user chooses it)

Commits updated vendored submodule pointers in the supex repo and pushes the `supex-patches` branches to GitHub. This ensures submodule pointers on GitHub always reference reachable commits.

1. Check which submodules have changed pointers:
   ```
   git diff --submodule=short -- vcad/vendor/
   git diff --cached --submodule=short -- vcad/vendor/
   ```
   If no submodule pointers changed, report "nothing to commit" and stop.

2. Push ALL changed submodules first, before any commits:
   ```
   git -C vcad/vendor/<name> push darwin supex-patches
   ```
   If any push fails, STOP and report the error — do NOT commit any pointers. If some pushes succeed and others fail, report partial state and let user decide.

3. After all pushes succeed, create a **separate commit** for each changed submodule:
   ```
   git add vcad/vendor/<name>
   git commit -m "Roll <name> vendor on top of <old-upstream>..<new-upstream>

   https://github.com/ecto/<name>/compare/<old-upstream>...<new-upstream>"
   ```
   Use the `<old-upstream>` and `<new-upstream>` values recorded in Phase 1 (the upstream `origin/main` before and after fetch). These represent the new upstream commits incorporated by the rebase. Do NOT use the submodule pointer SHAs — those are our rebased patch commits which get new SHAs on every roll.

   Only stage one submodule pointer per commit — never bundle multiple submodules or other files.

### Important

- Push MUST succeed before committing — a commit with unreachable submodule pointers breaks `git clone --recurse-submodules`
