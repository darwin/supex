---
name: review-vendor
description: Fetch upstream changes in vendored submodules and review their impact on supex
---

Review new upstream changes in vendored submodules and analyze their impact on the supex sidecar before deciding whether to roll.

All paths below are relative to the supex repo root.

### Arguments

Optional repo names: `tang`, `loon`, `phyz`, `vcad` (matching directory names under `vcad/vendor/`).

- **No arguments** — process all repos in default order: tang, loon, phyz, vcad
- **One or more names** — process only those repos, in the order given

Examples: `/review-vendor vcad`, `/review-vendor loon vcad`

### Submodule types

There are two kinds of vendored submodules:

- **Patch repos** (`vcad/vendor/loon`, `vcad/vendor/phyz`, `vcad/vendor/vcad`) — have a darwin fork with a `supex-patches` branch that carries local patches rebased on top of upstream `origin/main`.
- **Plain repos** (`vcad/vendor/tang`) — track upstream `origin/main` directly, no fork, no patches.

## Phase 1: Fetch + changelog

Process selected submodules sequentially (default order: tang, loon, phyz, vcad).

### For each submodule:

1. Record the current upstream base before fetch: `git -C <sub> rev-parse origin/main` → save as `<old-upstream>`
2. Fetch upstream only: `git -C <sub> fetch origin`
3. Record the new upstream head: `git -C <sub> rev-parse origin/main` → save as `<new-upstream>`
4. If `<old-upstream>` == `<new-upstream>`, report "no new upstream commits" and skip to the next submodule
5. If there are new commits, display:
   - Number of new commits: `git -C <sub> rev-list --count <old-upstream>..<new-upstream>`
   - Commit log: `git -C <sub> log --oneline <old-upstream>..<new-upstream>`
   - Changed files summary: `git -C <sub> diff --stat <old-upstream>..<new-upstream>`
   - GitHub compare link: `https://github.com/ecto/<name>/compare/<old-upstream>...<new-upstream>`

Save the `<old-upstream>` and `<new-upstream>` pair for each submodule with new commits — these are needed in Phase 2 and Phase 3.

### Important

- Do NOT fetch darwin fork — this review is about upstream changes only
- Do NOT modify any branches, rebase, or change worktree state — Phase 1 and 2 are read-only (fetch is the only network operation)

## Phase 2: Impact analysis

For each submodule that has new upstream commits, analyze the impact on supex.

### Step 1: Read the upstream diff

Read the actual diff for each changed submodule:
```
git -C <sub> diff <old-upstream>..<new-upstream>
```

If the diff is very large (thousands of lines), focus on files that are likely to affect supex:
- Public API changes (pub fn, pub struct, pub enum, pub trait)
- Changes to crate root lib.rs or mod.rs files
- Cargo.toml dependency changes
- Files matching crates used by sidecar (see dependency surface below)

### Step 2: Cross-reference with supex dependency surface

Read the supex integration points to understand what APIs are actually used:

- `vcad/sidecar/src/evaluator.rs` — main integration point:
  - loon-lang: `parse()`, `eval_program_with_env_and_base_dir()`, `Value` ADT variants
  - vcad-loon: `value_to_document()`, `VCAD_LIB_SOURCE`
  - vcad-eval: `evaluate_document()`, `EvalOptions`, `EvaluatedScene`, `EvaluatedPart`
  - vcad-ir: `Document`
  - vcad-kernel-primitives: `BRepSolid` (volume, surface_area, bounding_box, brep, is_empty)
  - vcad-kernel-tessellate: `TessellationParams`

- `vcad/sidecar/src/dae_export.rs` — BRep export:
  - vcad-kernel-geom: `GeometryStore`, `SurfaceKind`
  - vcad-kernel-math: `Point2`, `Vec3`
  - vcad-kernel-topo: `Topology`, `Orientation`, half-edge navigation
  - vcad-kernel-tessellate: `tessellate_face`

- `vcad/sidecar/Cargo.toml` — crate versions and features

### Step 3: Report per submodule

For each submodule with changes, report:

1. **Breaking changes** — renamed/removed public types, functions, or methods; changed signatures; modified struct fields; changed enum variants used by supex
2. **New features** — new public API, types, or modules that supex could leverage
3. **Bug fixes** — fixes that may change behavior supex depends on
4. **Summary** — what is happening in this upstream repo, development direction

### Step 4: Overall assessment

After all submodules are analyzed, provide:

- **Roll risk**: low / medium / high — based on likelihood of breaking supex
- **Recommendation**: whether to roll now, wait, or roll with caution
- **Action items**: specific things to watch for or adjust in supex if rolling

## Phase 3: Optional build test

After the analysis, **ask the user** whether they want to test build compatibility.

If the user declines, the command ends here — repos remain unchanged (only the fetch from Phase 1 happened).

If the user agrees, proceed:

### Dirty worktree check

Before modifying any repo, check for assume-unchanged files:
1. Run `git -C <sub> ls-files -v | grep ^h` for each submodule
2. If any found, STOP and tell the user — explain which files have the flag
3. Let the user decide how to handle it — do NOT automatically reset or stash

### Rebase

For each selected submodule with new upstream commits:

**Plain repos (tang):**
- Fast-forward: `git -C <sub> pull --ff-only origin main`

**Patch repos (loon, phyz, vcad):**
- Ensure on `supex-patches` branch (restore from darwin if detached): `git -C <sub> checkout -B supex-patches darwin/supex-patches`
- Rebase: `git -C <sub> rebase origin/main`
- If rebase fails with conflicts, STOP and assist with resolution

### Build + test

1. Rebuild: `./scripts/rebuild.sh`
2. If rebuild fails, STOP and report — do not run tests
3. Test: `./test`
4. Report results (pass/fail, which tests failed if any)

### After build test

Ask the user what to do next:

- **Keep** — leave repos rebased (ready for commit via `commit-vendor`)
- **Revert** — reset each submodule to its previous state:
  - For patch repos: `git -C <sub> checkout -B supex-patches darwin/supex-patches`
  - For plain repos: `git -C <sub> checkout <old-upstream>`
