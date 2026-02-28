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
| `phyz/`   | `ecto/phyz`           |
| `tang/`   | `ecto/tang`           |

## Workflow

Two Claude Code commands manage the vendor update cycle:

1. **`/review-vendor`** — fetch upstream changes, display changelog, analyze
   impact on the sidecar, optionally rebase and test build. Read-only until
   the user opts into the build test phase.

2. **`/commit-vendor`** — push `supex-patches` branches to GitHub and commit
   the updated submodule pointers. Must be run after a successful review +
   build test. Each submodule gets its own commit with a GitHub compare link.

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
git config submodule.vcad/vendor/phyz.ignore dirty
```
