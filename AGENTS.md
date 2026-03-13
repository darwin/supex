# AGENTS.md

Guidance for AI agents (Claude, Codex, Gemini, ...) when working on this repository.

`CLAUDE.md` is a symlink to this file for Claude Code compatibility.

## Branch Strategy

- **`main`**: Stable releases only. Do not commit directly.
- **`dev`**: Active development. All work here.

## Guidelines

- **NEVER bump version numbers** unless explicitly asked
- **NEVER commit changes** unless explicitly asked
- **NEVER read git-ignored files** unless explicitly asked
- **NEVER use emojis** in documentation
- **NEVER include `vcad/vendor/*` submodule pointer changes in regular commits** — use the `commit-vendor` skill instead, which pushes branches to GitHub first. Committing submodule pointers without pushing makes the repo uncloneable. If the user explicitly asks to commit vendor changes manually, warn them that they MUST push `supex-patches` branches to GitHub before or immediately after.
- **Use `git ls-tree -r HEAD`** to find project files
- **Use portable shebangs** - `#!/usr/bin/env bash`, `#!/usr/bin/env python3`, etc.

## For AI Agents — Common Mistakes

```bash
# WRONG — git add includes vendor submodule pointer changes
git add -A && git commit -m "Add feature"

# CORRECT — exclude vendor, use commit-vendor skill for submodule changes
git add driver/ runtime/
git diff --cached --name-only | grep -v vcad/vendor/
```

```bash
# WRONG — debug build (SketchUp loads release binary)
cargo build --manifest-path vcad/sidecar/Cargo.toml

# CORRECT — always build release
cargo build --release --manifest-path vcad/sidecar/Cargo.toml
```

```bash
# WRONG — find/ls to discover project files (misses git-ignored state)
find . -name "*.rb"

# CORRECT — git ls-tree shows tracked files only
git ls-tree -r HEAD --name-only | grep '\.rb$'
```

## Project Structure

```
supex/
├── driver/                    # Python MCP driver + CLI
│   └── src/supex_driver/
│       ├── cli/               # CLI commands
│       ├── connection/        # SketchUp socket connection
│       └── mcp/               # MCP server
├── runtime/                   # Ruby SketchUp extension
│   └── src/
│       ├── supex_runtime.rb   # Extension entry point
│       └── supex_runtime/     # Extension modules
├── vcad/                      # VCAD integration
│   ├── sidecar/               # Rust VCAD evaluator (BRep pipeline)
│   ├── viewer/                # Standalone Tauri geometry viewer
│   └── vendor/                # Git submodules (vcad, loon, phyz)
│       ├── vcad/              # BRep CAD kernel
│       ├── loon/              # Loon language
│       └── phyz/              # Physics engine
├── docs/                      # Documentation
│   └── agents/                # Agent prompts (guide/ symlinked as supex-guide/)
├── devtools/                  # Developer tools
│   ├── docgen/                # SketchUp API doc generator
│   └── radar/                 # Log aggregator / observability
├── stdlib/                    # Standard library (Ruby helpers)
├── scripts/                   # Development scripts
└── examples/                  # Example projects (orphan branches)
```

## Architecture

MCP-based platform connecting AI agents to SketchUp:

- **Python MCP Driver** (`driver/`) - FastMCP server exposing tools to AI
- **Ruby Runtime** (`runtime/`) - SketchUp extension executing commands
- **Socket Communication** - TCP on localhost:9876 (default)

## Development Commands

```bash
# Launch SketchUp with extension
./scripts/launch-sketchup.sh

# CLI commands
./supex status
./supex info
./supex reload

# Run all tests
./test

# Run selected test suites (slugs: driver, stdlib, runtime, mock, sidecar, viewer, radar, e2e)
./test viewer sidecar
./test --list          # show available suites

# Rebuild binaries (slugs: sidecar, viewer)
./scripts/rebuild.sh                   # rebuild all
./scripts/rebuild.sh sidecar           # rebuild only sidecar

# Build production .rbz
cd runtime && bundle exec rake build
```

## Key Files

**Driver (Python):**
- `driver/src/supex_driver/mcp/mcp_server.py` - MCP server and tools
- `driver/src/supex_driver/mcp/vcad_tools.py` - VCAD MCP tools
- `driver/src/supex_driver/connection/sketchup_connection.py` - SketchUp socket connection
- `driver/src/supex_driver/connection/vcad_connection.py` - VCAD sidecar connection
- `driver/src/supex_driver/cli/main.py` - CLI implementation

**Runtime (Ruby):**
- `runtime/src/supex_runtime.rb` - Extension loader
- `runtime/src/supex_runtime/main.rb` - Main extension code

**Scripts:**
- `scripts/launch-sketchup.sh` - Development launcher
- `mcp` - MCP server entry point
- `supex` - CLI entry point

## Naming Conventions

- **VCAD** is an acronym — always write "VCAD" in prose (docs, comments, docstrings, log messages), never "vcad"
- Lowercase `vcad` is correct in identifiers (`vcad_place`, `vcad_connection`), file paths (`vcad/sidecar/`), logger names (`supex.vcad`), and Rust crate names (`vcad-eval`, `vcad-kernel`)
- For library source files, prefer `.oo` extension (not `.loon`) in docs, examples, and generated project conventions

## VCAD Sidecar

Rust binary at `vcad/sidecar/`. Dependencies (vcad, loon, phyz) are vendored as git submodules in `vcad/vendor/`. After cloning, run `git submodule update --init --recursive` if you didn't use `--recurse-submodules`.

The vcad submodule requires `npm install` in `vcad/vendor/vcad/` for font assets used at compile time. This modifies the tracked `package-lock.json` — tell git to ignore the change:

```bash
cd vcad/vendor/vcad
npm install
git update-index --assume-unchanged package-lock.json Cargo.lock
# local-only ignore for node_modules and IDE files (not committed to vcad repo)
echo -e "node_modules/\n*.iml" >> $(git rev-parse --git-dir)/info/exclude
```

Also exclude IDE files in loon and phyz:

```bash
for repo in loon phyz; do
  echo "*.iml" >> $(git -C vcad/vendor/$repo rev-parse --git-dir)/info/exclude
done
```

During development, vendor submodules often show as dirty in `git status` (untracked build artifacts, modified files). Silence this noise in the parent repo:

```bash
git config submodule.vcad/vendor/vcad.ignore dirty
git config submodule.vcad/vendor/loon.ignore dirty
git config submodule.vcad/vendor/phyz.ignore dirty
```

This only hides working-tree dirt — committed HEAD pointer changes still show up (which is what you want).

After a vendor roll (submodule update), Cargo may retain stale `.rmeta` cache because git doesn't always update file mtimes. This causes `cargo check` (and IDE diagnostics) to report false errors while `cargo build` succeeds. Fix by clearing the affected crates:

```bash
cargo clean -p vcad-ir -p vcad-eval --manifest-path vcad/sidecar/Cargo.toml
```

In IntelliJ IDEA, follow up with **Refresh Cargo Projects** in the Build tool window.

After any code change that affects the sidecar:

1. **Rebuild release binary** (SketchUp uses release, not debug):
   ```bash
   cargo build --release --manifest-path vcad/sidecar/Cargo.toml
   ```
2. **Restart the running sidecar** — kill the old process and relaunch:
   ```bash
   kill $(pgrep -f supex-vcad-sidecar)
   sleep 1
   SUPEX_WORKSPACE=$WORKSPACE scripts/launch-vcad-sidecar.sh &
   ```
   `$WORKSPACE` is the user's project directory (e.g. an `example-*` project).
3. **Verify** with `check_status` or `vcad_place`.

Temp directory is resolved as: `SUPEX_VCAD_TEMP_DIR` (explicit) > `SUPEX_WORKSPACE/.tmp/vcad-sidecar` (derived). If neither env var is set, the sidecar panics at startup.

## Observability with Radar

Radar (`devtools/radar/`) is a log aggregator that tails all supex subsystem logs in real-time. It normalizes events from MCP protocol, runtime console, CLI, and VCAD sidecar into a unified stream. Each event gets a deterministic 6-char hex EID (e.g. `a1b2c3`).

### Agent workflow

Run two radar instances during a session for full observability:

1. **Background stream** — plain text output for automated monitoring:
   ```bash
   ./radar watch --plain              # streams events to stdout
   ./radar watch --plain -l WARN      # only warnings and errors
   ./radar watch --plain -s mcp-protocol,vcad-sidecar
   ```

2. **Interactive pane** — TUI in a separate tmux pane for drill-down:
   ```bash
   ./radar watch                      # launches TUI
   ```
   Use `j`/`k` to browse events, `Enter` to open detail panel (shows full event with EID), `Tab` to toggle raw view, `/` to search.

Cross-reference events between the two: the `--plain` stream prints `[e:EID]` per line, and the TUI detail panel shows the same EID. Use this to find an event in the plain stream and inspect its full detail in the TUI (or vice versa).

### Filtering

```bash
./radar watch -l ERROR                  # minimum log level
./radar watch -s runtime-console        # specific source(s)
./radar watch -s mcp-protocol,vcad-sidecar -l WARN
```

Available sources: `mcp-protocol`, `mcp-stderr`, `cli-driver`, `cli-stdout`, `cli-stderr`, `runtime-console`, `runtime-stdout`, `runtime-stderr`, `vcad-sidecar`, `vcad-events`.

## Agent Prompts Convention

User projects symlink `docs/agents/guide/` as `supex-guide/` in their project root. Therefore:

- Files in `docs/agents/guide/` (README.md, workflow.md, etc.) should reference paths as `supex-guide/...`
- The exception is `docs/agents/README.md` which uses repository-relative paths because it describes this repository's structure for human readers, not agent consumption
