# Vendored submodules

Git submodules providing the VCAD evaluation pipeline and its dependencies
for the supex sidecar (`vcad/sidecar/`).

## Submodule types

There are two kinds of vendored submodules:

**Patch repos** — have a darwin fork on GitHub with a `supex-patches` branch
that carries local patches rebased on top of upstream `origin/main`.

| Directory | Upstream              | Fork                   |
|-----------|-----------------------|------------------------|
| `loon/`   | `ecto/loon`           | `darwin/loon`          |
| `vcad/`   | `ecto/vcad`           | `darwin/vcad`          |

**Plain repos** — track upstream `origin/main` directly, no fork, no patches.

| Directory | Upstream              |
|-----------|-----------------------|
| `tang/`   | `ecto/tang`           |

`phyz` is deliberately not vendored: upstream vcad pins it in its
`[workspace.dependencies]` as a git dependency with a fixed `rev`, so Cargo
fetches it on demand when the full vcad workspace is built. The supex
sidecar never resolves it.

## Workflow

Two Claude Code commands manage the vendor update cycle:

1. **`/review-vendor`** — fetch upstream changes, display changelog, analyze
   impact on the sidecar, optionally rebase and test build. Read-only until
   the user opts into the build test phase.

2. **`/commit-vendor`** — archive old `supex-patches` HEAD as a tag
   (`archive/<sha>`), push rebased branches, and commit the updated submodule
   pointers. Each submodule gets its own commit with a GitHub compare link.
   Archive tags prevent GitHub from garbage-collecting commits referenced by
   older supex history.

Typical flow: `/review-vendor` &#8594; inspect results &#8594; `/commit-vendor`.

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
