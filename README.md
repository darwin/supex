> **Note**: Unless you explicitly switched, you are viewing the `main` branch which contains stable releases. Active development happens on the [`dev` branch](https://github.com/darwin/supex/tree/dev).

![Supex Hero](assets/supex-hero-poster.png)

# Supex: SketchUp Automation for Agentic Coding

An experimental platform that brings [agentic coding](https://www.claude.com/blog/introduction-to-agentic-coding) to [SketchUp](https://www.sketchup.com). Describe what you want to build in natural language, and let AI write and execute scripts against SketchUp. Designed for programmers who want to augment their 3D modeling workflow with AI assistance and direct API access.

> **Early Stage Project**: Supex is in very early development, tested only on macOS with [Claude Code](https://claude.ai/code) and the latest SketchUp version. Programmers with existing agentic coding experience will get the most out of it.

## Motivation

I'm Antonin, a programmer who discovered the power of agentic coding. Working with Claude Code on git-versioned projects changed how I think about software development - describing intent in natural language, iterating rapidly, and having full history of every change.

When I started a SketchUp project for my house renovation, I wondered if similar workflow could be used. Not to replace direct modeling in SketchUp's GUI - that's still the best way to sketch ideas and make quick adjustments. But for repetitive tasks, parametric designs, and complex geometry, I wanted to describe what I need and let AI figure out the code.

Supex bridges these two worlds: keep using SketchUp's intuitive interface for direct manipulation, while having AI handle the scripting when you need precision, automation, or just want to say "create a staircase with 15 steps" instead of drawing it manually.

## Key Features

- **Full SketchUp Ruby API** — execute any operation via Ruby code, inline or from project scripts
- **Model introspection** — entity inspection, screenshots, materials, camera, model statistics
- **Project-based workflow** — scripts in git, IDE support with syntax highlighting and linting
- **Export** — SKP, OBJ, STL, PNG, JPG formats

## VCAD Integration

VCAD is a BRep (Boundary Representation) kernel that brings parametric CAD modeling to SketchUp. The AI agent writes geometry code in [Loon](https://loonlang.com/) (a Lisp with algebraic data types and type inference), a Rust sidecar evaluates it into solid geometry, and SketchUp imports the resulting mesh as a native component.

```
.cmp.oo source → Loon → VCAD IR → BRep → mesh → SketchUp
```

**Modeling operations**: primitives, booleans (union/difference/intersection), fillet, chamfer, shell, extrude, revolve, sweep, loft, linear and circular patterns. Live preview in a standalone Tauri viewer.

For the full capability list and tooling details, see [VCAD Integration](docs/vcad.md).

## Architecture Overview

Supex bridges AI agents and CLI tools with SketchUp through a client-server architecture:

![Architecture Overview](assets/supex-architecture-poster.png)

- **Python Driver** — [MCP](https://modelcontextprotocol.io) server (`./mcp`) and CLI (`./supex`) for AI agents and human use
- **Ruby Runtime** — SketchUp extension with bridge server, stdlib, and REPL (`./repl`)
- **VCAD Sidecar** — Rust server evaluating Loon code into BRep geometry (`./vcad-sidecar`)
- **VCAD Viewer** — Standalone Tauri app for live BRep preview
- **Radar** — Log aggregator TUI that tails all subsystems in one stream (`./radar`)

Communication via JSON-RPC 2.0 over TCP sockets. For more details, see [Architecture](docs/architecture.md).

## How It Works

Scripts live in your git-versioned project directory. The AI agent writes code, executes it via MCP tools, verifies results with screenshots and introspection, and iterates — all automatically.

```
your-project/
├── src/
│   ├── create_table.rb    # Ruby scripts for SketchUp API
│   ├── walls.cmp.oo       # Loon/VCAD parametric geometry
│   └── materials.rb
├── models/
│   └── project.skp
└── .mcp.json              # MCP client configuration
```

## Installation & Setup

### Requirements

- **SketchUp 2026** - Download from [sketchup.com](https://www.sketchup.com)
  - Only the latest SketchUp version is tested
  - Project is experimental - no backward compatibility guarantees
- **Claude Code** - AI-powered development environment from [claude.ai/code](https://claude.ai/code)
  - Only tested with Claude Code (experimental project)
  - Other MCP-compatible AI agents might work but are untested
- **macOS** - Currently the primary supported platform
- **Python 3.14+** - For the MCP driver (managed via UV)
- **Ruby 3.2.2** - Same as the Ruby version bundled with SketchUp 2025/2026. This Ruby is past upstream end-of-life, but the pin cannot move until SketchUp ships a newer Ruby, because the runtime must run on the interpreter embedded in SketchUp

### 1. Clone the Repository

```bash
git clone --recurse-submodules https://github.com/darwin/supex.git
cd supex
```

Supex uses git submodules for vendored VCAD dependencies (`vcad/vendor/`). If you cloned without `--recurse-submodules`, run:

```bash
git submodule update --init --recursive
```

### 2. Launch SketchUp with Extension

The development launcher handles extension deployment automatically:

```bash
./scripts/launch-sketchup.sh path/to/your/model.skp
```

This script:
- Launches the installed SketchUp app
- Deploys Ruby extension sources directly (no .rbz building required)
- Enables live reloading during development
- Optionally opens a model given as parameter  

### 3. Configure Claude Code

In your project directory, register the Supex MCP server and link the agent guide:

```bash
claude mcp add --scope project --transport stdio supex -- /path/to/supex/mcp
ln -s /path/to/supex/docs/agents/guide supex-guide
```

The first command writes `.mcp.json` next to your project. The symlink gives the agent access to the
Supex guide (workflow rules, tool reference, SketchUp API docs); reference `supex-guide/README.md`
from your project's `CLAUDE.md`. Add both `.mcp.json` and `supex-guide` to `.gitignore`, since the
paths vary per developer. Replace `/path/to/supex` with the actual path to your Supex checkout.

### 4. Verify Connection

```bash
./supex status
```

You should see connection status and SketchUp version information.

## Quick Start

For a complete step-by-step tutorial, see the **[Simple Table Example](https://github.com/darwin/supex/tree/example-simple-table)**.

Example projects live in separate orphan branches. To clone an example:

```bash
git clone -b example-simple-table https://github.com/darwin/supex.git simple-table
cd simple-table
ln -s /path/to/supex/docs/agents/guide supex-guide
```

The example covers:
1. Project setup and configuration
2. Creating geometry with Ruby scripts
3. Using introspection tools to verify results
4. Iterative development workflow

## Development

Run tests and linters from the repository root:

```bash
# Run all tests (driver, stdlib, runtime, mock, sidecar, viewer, radar)
./test

# Run selected test suites
./test sidecar viewer

# List available test suites
./test --list

# Run E2E tests only (requires SketchUp running)
./test --e2e

# Run all linters (RuboCop, ruff, mypy, rustfmt, clippy, tsc, eslint)
./scripts/lint.sh

# Rebuild Rust binaries (VCAD sidecar, viewer)
./scripts/rebuild.sh
./scripts/rebuild.sh sidecar   # rebuild only sidecar

# Run the same Docker image as CI locally (requires Docker)
./scripts/docker-test.sh
```

## Reference

- **[Documentation Index](docs/README.md)** - Start here for docs navigation
- **[CLI Reference](docs/cli.md)** - Command-line interface for direct SketchUp interaction
- **[Interactive REPL](docs/repl.md)** - Interactive Ruby development in SketchUp
- **[MCP Reference](docs/agents/guide/mcp.md)** - Tools available for AI agents (Claude Code)
- **[Configuration](docs/configuration.md)** - Environment variables and settings
- **[Protocol](docs/protocol.md)** - JSON-RPC communication protocol details
- **[Security](docs/security.md)** - Authentication, path restrictions, and recommendations
- **[VCAD Integration](docs/vcad.md)** - Parametric BRep CAD via Loon language
- **[Troubleshooting](docs/agents/guide/troubleshooting.md)** - Common issues and solutions
