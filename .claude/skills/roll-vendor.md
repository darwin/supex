# Roll vendor

Trigger: user says "roll vendor", "roll deps", "update vendor", "rebase vendor"

## What this does

Rebases `supex-patches` branches in vendored submodules (loon, phyz, vcad) on top of latest upstream changes.

## Steps

For each submodule in `vcad/vendor/loon`, `vcad/vendor/phyz`, `vcad/vendor/vcad`:

1. Fetch from both remotes: `git -C <submodule> fetch origin && git -C <submodule> fetch darwin`
2. Check for dirty state (see below)
3. Check current branch — may be `supex-patches` or detached HEAD
4. If detached HEAD: restore `supex-patches` from darwin fork: `git -C <submodule> checkout -B supex-patches darwin/supex-patches`
5. Rebase `supex-patches` onto upstream main: `git -C <submodule> rebase origin/main`
6. Show new upstream commits summary

All paths are relative to the supex repo root.

## Dirty worktree handling

Vendor repos may appear clean in `git status` but have hidden local changes due to `assume-unchanged` flags or `.gitmodules` `ignore = dirty` settings. This is intentional — we pin Cargo.lock locally.

**Before rebasing each repo:**
1. Run `git -C <submodule> ls-files -v | grep ^h` to detect assume-unchanged files
2. If any found, **STOP and tell the user** — explain which files have the flag and that they need to be resolved before rebase can proceed
3. Typical resolution: `git update-index --no-assume-unchanged <file>` then `git checkout -- <file>` or `git stash`
4. Let the user decide how to handle it — do NOT automatically reset or stash

## After rolling

Do NOT automatically commit or run tests. Instead, offer the user:
1. **Rebuild**: `cargo build --release` for the sidecar
2. **Test**: `./scripts/launch-tests.sh` to run all headless tests
3. **Commit**: `git add vcad/vendor/<repo>` + commit with message format:
   ```
   Roll <repo> vendor <old-sha>..<new-sha>

   https://github.com/ecto/<repo>/compare/<old-sha>...<new-sha>
   ```
   Where `<old-sha>` is the previous submodule commit and `<new-sha>` is the new HEAD after rebase. The GitHub compare URL lets reviewers see the full upstream diff in browser.

Let the user choose which of these to do and in what order.

## Important

- Run repos sequentially, not in parallel — user needs to see progress and handle conflicts
- If rebase fails with conflicts, STOP and report which repo has conflicts — do NOT abort the rebase automatically
- Proactively assist with conflict resolution: show the conflicting files, read them, explain what both sides changed, and suggest a resolution — but always let the user confirm before proceeding
- Report summary at the end: which repos were rolled, how many new commits were pulled in, which had no changes
