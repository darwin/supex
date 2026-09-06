---
name: review-vendor
description: Fetch upstream changes in vendored submodules and review their impact on supex
---

Review new upstream changes in vendored submodules and analyze their impact on the supex sidecar before deciding whether to roll.

All paths below are relative to the supex repo root.

### Submodule types

There are two kinds of vendored submodules:

- **Patch repos** (`vcad/vendor/loon`, `vcad/vendor/vcad`) — have a darwin fork with a `supex-patches` branch that carries local patches rebased on top of upstream `origin/main`.
- **Plain repos** (`vcad/vendor/tang`) — track upstream `origin/main` directly, no fork, no patches.

### Workspace coupling — why tang must move with vcad

`tang` is not an independent upstream dependency. It is a **sibling crate inside the vcad workspace**: vcad path-depends on it (`tang = { path = "../tang/crates/tang", version = "0.2" }` in vcad's `[workspace.dependencies]`, mirrored in `[patch.crates-io]`). The minimum tang version is therefore **dictated by the pinned vcad commit**, not by what supex itself calls.

This means the right question for rolling tang is **"does the vcad commit we're pinning require a newer tang?"** — NOT "does the supex sidecar use autodiff?". The sidecar is a *separate* Cargo workspace that cherry-picks only a few `vcad-kernel-*` crates, so its build can stay green even when tang lags. But rolling vcad forward while leaving tang behind records an **internally inconsistent vendored vcad workspace**: anything that resolves the full vcad graph (the native app `apple/VcadApp` via `vcad-ffi`, `cargo check` / IDE diagnostics at the vcad root, `just clear-rust-caches`, vcad CLI/sim, vcad CI) fails dependency resolution. Roll tang **in lockstep with vcad** to keep that workspace buildable.

`phyz` is **not vendored**. Upstream vcad pins it as a git dependency with a fixed `rev` in `[workspace.dependencies]`, so Cargo fetches the right commit on demand (network required for the full-graph check). Nothing in supex references phyz directly.

## Phase 1: Fetch + changelog

Process all submodules in order: tang, loon, vcad.

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

### Step 2b: vcad workspace consistency check (tang version floor)

This step catches the lockstep coupling described in "Workspace coupling" above. It is independent of the sidecar dependency surface — tang can need rolling even when the sidecar never touches it.

For the **vcad commit being rolled to** (`<new-upstream>` of the vcad submodule, or its rebased `supex-patches` tip), read the version constraints vcad places on tang:

```
# tang constraint(s) required by the rolled vcad
git -C vcad/vendor/vcad show <vcad-new>:Cargo.toml | grep -E '^\s*tang(-la|-expr)?\s*='
```

Then compare against the tang version the rolled pointer would provide:

```
git -C vcad/vendor/tang show <tang-new>:crates/tang/Cargo.toml | grep -m1 '^version'
git -C vcad/vendor/tang show <tang-new>:Cargo.toml | grep -m1 '^version'   # workspace version used by tang-la / tang-expr
```

Report a **blocking inconsistency** if the rolled vcad requires a tang version that the (rolled or current) tang pointer does not satisfy. In that case tang MUST be rolled forward to a commit whose version satisfies vcad's constraint — even if Step 2 found no sidecar API usage. Note this explicitly in the Step 4 assessment and action items.

Also note the phyz `rev` pinned by the rolled vcad (`grep -E '^\s*phyz\s*=' Cargo.toml`) in the report — it is informational only, Cargo resolves it from GitHub.

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

For each submodule with new upstream commits:

**Plain repos (tang):**
- Fast-forward: `git -C <sub> pull --ff-only origin main`

**Patch repos (loon, vcad):**
- Ensure on `supex-patches` branch (restore from darwin if detached): `git -C <sub> checkout -B supex-patches darwin/supex-patches`
- Rebase: `git -C <sub> rebase origin/main`
- If rebase fails with conflicts, STOP and assist with resolution

### Build + test

1. Rebuild: `./scripts/rebuild.sh`
2. If rebuild fails, STOP and report — do not run tests
3. Test: `./test`
4. Report results (pass/fail, which tests failed if any)

**Note — sidecar rebuild does NOT validate the full vcad workspace.** `./scripts/rebuild.sh` only builds the sidecar (a separate workspace that never resolves `vcad-kernel-physics`), so it stays green even when the tang floor from Step 2b is violated. To actually prove the vendored vcad workspace resolves, build something that resolves the full graph, e.g.:

```
cargo check --manifest-path vcad/vendor/vcad/Cargo.toml -p vcad-ffi
```

If Step 2b flagged an inconsistency, this is where it surfaces as a `failed to select a version for the requirement` resolution error.

Note: the rebuild will likely modify `vcad/sidecar/Cargo.lock` — this is expected. It will be committed together with the submodule pointers by `commit-vendor`.

### After build test

Ask the user what to do next:

- **Keep** — leave repos rebased (ready for commit via `commit-vendor`)
- **Revert** — reset each submodule to its previous state:
  - For patch repos: `git -C <sub> checkout -B supex-patches darwin/supex-patches`
  - For plain repos: `git -C <sub> checkout <old-upstream>`
