# CLAUDE.md

Guidance for Claude Code when working on this repository.

## Branch Strategy

- **`main`**: Stable releases only. Do not commit directly.
- **`dev`**: Active development. All work here.

## Guidelines

- **NEVER bump version numbers** unless explicitly asked
- **NEVER commit changes** unless explicitly asked
- **NEVER read git-ignored files** unless explicitly asked
- **NEVER use emojis** in documentation
- **Use `git ls-tree -r HEAD`** to find project files
- **Use portable shebangs** - `#!/usr/bin/env bash`, `#!/usr/bin/env python3`, etc.

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
├── docs/                      # Documentation
│   └── agents/                # Agent prompts (symlinked as supex-docs/)
├── docgen/                    # SketchUp API doc generator
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

# Run tests
cd driver && uv run pytest tests/

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

Rust binary at `vcad/sidecar/`. After any code change that affects the sidecar:

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
3. **Verify** with `check_sketchup_status` or `vcad_place`.

Temp directory is resolved as: `VCAD_TEMP_DIR` (explicit) > `SUPEX_WORKSPACE/.tmp/vcad-sidecar` (derived). If neither env var is set, the sidecar panics at startup.

## Agent Prompts Convention

User projects symlink `docs/agents/` as `supex-docs/` in their project root. Therefore:

- Files in `docs/agents/` (prompt.md, workflow.md, etc.) should reference paths as `supex-docs/...`
- The exception is `README.md` which uses `docs/agents/` because it describes this repository's structure for human readers, not agent consumption
