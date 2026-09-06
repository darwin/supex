# Vendored submodules

Git submodules providing the VCAD evaluation pipeline and its dependencies
for the supex sidecar (`vcad/sidecar/`).

## Submodules

All vendored submodules track upstream `origin/main` directly. There are no
forks and no local patch branches: a submodule pointer is always an upstream
commit, so `git clone --recurse-submodules` works without extra remotes. The
sidecar is written against upstream APIs only; when it needs a change in a
vendored crate, the change goes upstream as a PR, never into a patch branch.

| Directory | Upstream    | Role                                                    |
|-----------|-------------|---------------------------------------------------------|
| `vcad/`   | `ecto/vcad` | BRep CAD kernel and evaluation crates used by the sidecar |
| `loon/`   | `ecto/loon` | Loon language (parser and interpreter)                  |
| `tang/`   | `ecto/tang` | Autodiff; a sibling crate of the vcad workspace         |

`tang` is not an independent dependency of supex: vcad path-depends on it
(`../tang/crates/tang` in vcad's `[workspace.dependencies]`), so the required
tang version is dictated by the pinned vcad commit. Roll tang in lockstep with
vcad to keep the vendored vcad workspace resolvable.

`phyz` is deliberately not vendored: upstream vcad pins it in its
`[workspace.dependencies]` as a git dependency with a fixed `rev`, so Cargo
fetches it on demand when the full vcad workspace is built. The supex
sidecar never resolves it.

## Workflow

Two Claude Code commands manage the vendor update cycle:

1. **`/review-vendor`** — fetch upstream changes, display the changelog,
   analyze impact on the sidecar (including the tang version floor required by
   the rolled vcad), and optionally check out the new upstream heads and test
   build. Read-only until the user opts into the build test phase.

2. **`/commit-vendor`** — verify every changed pointer is reachable from its
   upstream remote, show a summary with GitHub compare links, and create one
   atomic commit with all changed submodule pointers (plus
   `vcad/sidecar/Cargo.lock` if the rebuild touched it). It pushes nothing.

Typical flow: `/review-vendor`, inspect the results, then `/commit-vendor`.

## Setup after clone

```bash
git submodule update --init --recursive

# Font assets required by vcad at compile time
cd vcad/vendor/vcad && npm install
git update-index --assume-unchanged package-lock.json Cargo.lock

# Silence dirty submodule noise in parent repo
git config submodule.vcad/vendor/vcad.ignore dirty
git config submodule.vcad/vendor/loon.ignore dirty
git config submodule.vcad/vendor/tang.ignore dirty
```
