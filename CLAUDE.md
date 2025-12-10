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
│   └── agents/                # Agent prompts for user projects
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
- `driver/src/supex_driver/mcp/server.py` - MCP server and tools
- `driver/src/supex_driver/connection/connection.py` - Socket connection
- `driver/src/supex_driver/cli/main.py` - CLI implementation

**Runtime (Ruby):**
- `runtime/src/supex_runtime.rb` - Extension loader
- `runtime/src/supex_runtime/main.rb` - Main extension code

**Scripts:**
- `scripts/launch-sketchup.sh` - Development launcher
- `mcp` - MCP server entry point
- `supex` - CLI entry point
