# Commit vendor

Trigger: user says "commit vendor", "push vendor", "vendor commit"

## What this does

Commits updated vendored submodule pointers in the supex repo and pushes the `supex-patches` branches to GitHub. This ensures submodule pointers on GitHub always reference reachable commits.

## Steps

1. Check which submodules have changed pointers:
   ```
   git -C <supex> diff --submodule=short -- vcad/vendor/
   git -C <supex> diff --cached --submodule=short -- vcad/vendor/
   ```
   If no submodule pointers changed, report "nothing to commit" and stop.

2. For each changed submodule, push `supex-patches` to `darwin` remote:
   ```
   git -C vcad/vendor/<name> push darwin supex-patches
   ```
   If push fails, STOP and report the error. Do NOT commit stale pointers.

3. Stage the submodule pointer changes:
   ```
   git -C <supex> add vcad/vendor/loon vcad/vendor/phyz vcad/vendor/vcad
   ```
   Only add submodules that actually changed — do NOT stage any other files.

4. Commit with a descriptive message listing what was updated, e.g.:
   ```
   Update vendored vcad, loon to latest supex-patches
   ```

## Important

- Push MUST succeed before committing — a commit with unreachable submodule pointers breaks `git clone --recurse-submodules`
- Only stage `vcad/vendor/*` submodule pointers — never include other changes in this commit
- If some pushes succeed and others fail, do NOT commit — report partial state and let user decide
