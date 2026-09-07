# AGENTS.md

Guidance for AI agents (Claude, Codex, Gemini, ...) working on this repository. `CLAUDE.md` is a symlink to
this file.

## Branch Strategy

- **`main`**: stable releases only, fast-forwarded by `scripts/release.sh`. Do not commit directly.
- **`dev`**: active development. All work happens here.

## Rules

- Commit after each finished logical unit and do not leave work uncommitted at the end of a task, unless
  the user explicitly asks you not to commit. Never push.
- Commit messages in English, imperative mood, no conventional-commits prefix (see `git log`).
- Stage only the files of your task. Never include `vcad/vendor/*` submodule pointer changes in a regular
  commit: use the `commit-vendor` skill. Every vendored submodule tracks upstream `main` without local
  patches, so a pointer must be an upstream commit or the repository becomes uncloneable. Changes a
  vendored crate needs go upstream as a PR.
- Never bump version numbers; `scripts/release.sh` does that on request.
- Never read git-ignored files unless explicitly asked.
- No emojis in documentation.
- Find project files with `git ls-tree -r HEAD --name-only`, not `find` or `ls`; the tree holds a lot of
  git-ignored state (generated docs, build output, `.tmp/`).
- Portable shebangs: `#!/usr/bin/env bash`, `#!/usr/bin/env python3`, ...

## Project Structure

```
supex/
├── .github/                   # GitHub Actions workflows and Dependabot config
├── driver/                    # Python MCP driver + CLI
│   └── src/supex_driver/
│       ├── cli/               # CLI commands
│       ├── connection/        # SketchUp socket connection, VCAD sidecar and viewer connections
│       └── mcp/               # MCP server (mcp_server.py, vcad_tools.py, vcad_diagnostics.py)
├── runtime/                   # Ruby SketchUp extension
│   ├── ide_stubs/             # Shims so IDEs resolve sketchup.rb / extensions.rb
│   └── src/
│       ├── supex_runtime.rb   # Extension entry point
│       └── supex_runtime/     # Extension modules (bridge_server.rb, tools.rb, path_policy.rb, ...)
├── stdlib/                    # Standard library (Ruby helpers), loaded into SketchUp by the runtime
├── mock/                      # Headless SketchUp API mock server (Ruby) for tests without SketchUp
├── vcad/                      # VCAD integration
│   ├── sidecar/               # Rust VCAD evaluator (BRep pipeline)
│   ├── viewer/                # Standalone Tauri geometry viewer
│   └── vendor/                # Git submodules: vcad, loon, tang (see vendor/README.md)
├── tests/                     # E2E tests (pytest) and the Ruby snippets they execute
├── docs/                      # Documentation (index in docs/README.md)
│   ├── agents/guide/          # Agent guide; user projects symlink it as supex-guide/
│   └── contracts/             # JSON schemas and example payloads for the wire protocol
├── devtools/                  # ci/ (Docker image), docgen/ (SketchUp API docs), radar/ (log aggregator)
├── assets/                    # README posters and the prompts that generated them
├── scripts/                   # Development scripts (launchers, rebuild, lint, release, docs check)
├── examples/                  # Example projects (orphan branches)
├── justfile                   # just recipes: sketchup, test, docs, lint, clear-rust-caches
├── supex, mcp, repl           # Root wrappers: CLI, MCP server, REPL client
└── test, radar, vcad-sidecar  # Root wrappers: test runner, radar TUI, VCAD sidecar
```

## Architecture

MCP platform connecting AI agents to SketchUp: the Python driver (`driver/`) exposes MCP tools and talks
over TCP (localhost:9876 by default) to the Ruby runtime (`runtime/`) running inside SketchUp. VCAD tools
send Loon sources to the Rust sidecar (`vcad/sidecar/`) and place the resulting meshes through the runtime.
Details: `docs/architecture.md`, wire protocol in `docs/protocol.md`.

## Development Commands

```bash
./scripts/launch-sketchup.sh [model.skp]   # SketchUp with the extension injected from source
./supex status                             # also: info, reload, entity <id>, eval-file, screenshot, ...
./test                                     # all non-E2E suites; ./test --list shows slugs
./test viewer sidecar                      # selected suites
./test --e2e                               # E2E against a real SketchUp; closes SketchUp when done
./scripts/lint.sh                          # every linter (RuboCop, ruff, mypy, rustfmt, clippy, tsc, eslint)
./scripts/check-docs.sh                    # markdownlint + guide self-containment
./scripts/rebuild.sh [sidecar|viewer]      # release binaries
./scripts/docker-test.sh [suites]          # the CI image locally
./scripts/release.sh 0.3.0                 # bump every component, commit, sign tag, fast-forward main
./scripts/changelog.sh v0.3.0              # GitHub Release changelog prompt into .tmp/
cd runtime && bundle exec rake build       # production .rbz
```

## Naming Conventions

- **VCAD** is an acronym: write "VCAD" in prose (docs, comments, docstrings, log messages), never "vcad".
  Lowercase `vcad` is correct in identifiers (`vcad_place`), paths (`vcad/sidecar/`), logger names
  (`supex.vcad`) and crate names (`vcad-eval`).
- Loon library sources use the `.oo` extension (not `.loon`) in docs, examples and generated projects.

## VCAD Sidecar

Setup after clone (submodules, `npm install` for font assets, ignoring the resulting lockfile churn and
dirty-submodule noise) is in `README.md` and `vcad/vendor/README.md`. After a vendor roll Cargo may keep
stale `.rmeta` caches, so `cargo check` and IDE diagnostics report false errors while `cargo build`
succeeds; `just clear-rust-caches` fixes it.

SketchUp runs the **release** binary. After any sidecar change:

1. `./scripts/rebuild.sh sidecar`
2. Restart the running sidecar: `kill $(pgrep -f supex-vcad-sidecar)`, then
   `SUPEX_WORKSPACE=<user project> scripts/launch-vcad-sidecar.sh &`
3. Verify with `check_status` or `vcad_place`.

The sidecar needs `SUPEX_VCAD_TEMP_DIR` or `SUPEX_WORKSPACE` (artifacts go to
`$SUPEX_WORKSPACE/.tmp/vcad-sidecar`); with neither it panics at startup.

## Observability

Radar (`devtools/radar/`) tails every supex log (MCP protocol, runtime console, CLI, VCAD sidecar and
events) into one stream; each event carries a 6-char EID shared between the plain stream and the TUI.
`./radar watch --plain -l WARN` for automated monitoring, `./radar watch` for the interactive TUI,
`-s <source,...>` to filter sources. Full reference: `devtools/radar/README.md`.

## Agent Guide Convention

User projects symlink `docs/agents/guide/` as `supex-guide/`, so the guide is read from two locations.
Inside the guide, reference other guide files and the symlinked `api/`, `stdlib/` and `cad-lib/`
directories by bare relative paths (`ruby.md`, `stdlib/README.md`) and never by repository-relative paths
(`docs/...`); nothing outside `docs/agents/guide/` is reachable from a user project.
`scripts/check-docs.sh` enforces this for links and bare-text paths. The exception is
`docs/agents/README.md`, which describes this repository for human readers.
