# Supex Driver

Python MCP server and CLI for SketchUp automation. Enables AI agents and command-line tools to execute Ruby code in SketchUp through the Model Context Protocol.

## Requirements

- Python 3.14 or later
- SketchUp with Supex Runtime extension installed

## Overview

Supex Driver is part of the Supex platform - a bridge between AI agents and SketchUp. It provides:

- **MCP Server**: 14 tools for AI agents via Model Context Protocol
- **CLI**: 14 commands for direct terminal interaction
- **Connection Layer**: TCP/JSON-RPC client for SketchUp runtime

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_HOST` | `localhost` | SketchUp runtime host |
| `SUPEX_PORT` | `9876` | SketchUp runtime port |
| `SUPEX_TIMEOUT` | `15.0` | Socket timeout in seconds |
| `SUPEX_RETRIES` | `2` | Max retry attempts |
| `SUPEX_LOG_DIR` | `~/.supex/logs` | Log file directory |
| `SUPEX_AGENT` | `user`/`mcp` | Agent identifier |

## MCP Tools

### Execution

| Tool | Description |
|------|-------------|
| `eval_ruby(code)` | Execute Ruby code directly |
| `eval_ruby_file(path)` | Execute Ruby script from file (preferred) |

### Introspection

| Tool | Description |
|------|-------------|
| `get_model_info()` | Entity counts, units, modified state |
| `list_entities(type)` | List geometry (all/faces/edges/groups/components) |
| `get_selection()` | Currently selected entities |
| `get_layers()` | All layers/tags |
| `get_materials()` | All materials with colors |
| `get_camera_info()` | Camera position and settings |
| `take_screenshot(output_path?)` | Save view to file |

### Model Management

| Tool | Description |
|------|-------------|
| `open_model(path)` | Open .skp file |
| `save_model(path?)` | Save model |
| `export_scene(format)` | Export: skp, obj, dae, stl, png, jpg |

### Status

| Tool | Description |
|------|-------------|
| `check_sketchup_status()` | Verify connection health |
| `console_capture_status()` | Ruby console capture info |

## CLI Commands

```bash
./supex <command> [options]
```

| Command | Description |
|---------|-------------|
| `status` | Check connection and docs status |
| `reload` | Reload extension |
| `eval <code>` | Execute Ruby code |
| `eval-file <path>` | Execute Ruby script |
| `info` | Model information |
| `entities [type]` | List entities |
| `selection` | Selected entities |
| `layers` | List layers |
| `materials` | List materials |
| `camera` | Camera info |
| `screenshot` | Capture view |
| `open <path>` | Open model |
| `save [path]` | Save model |
| `export <format>` | Export scene |

**Common Options:**
- `--host/-h` - SketchUp host (default: localhost)
- `--port/-p` - SketchUp port (default: 9876)
- `--raw/-r` - Output raw JSON

### Documentation Browser

```bash
./supex docs tree              # Show documentation hierarchy
./supex docs show <uri>        # View specific documentation
./supex docs search <term>     # Search documentation
```

## Example Usage

```ruby
# Create a simple box (execute via eval_ruby_file)
model = Sketchup.active_model
model.start_operation('Create Box', true)

group = model.entities.add_group
face = group.entities.add_face(
  [0, 0, 0], [1.m, 0, 0], [1.m, 1.m, 0], [0, 1.m, 0]
)
face.pushpull(50.cm)
group.name = 'Box'

model.commit_operation
```

For complete examples, see `examples/simple-table/`.

## Architecture

```
AI Agent / CLI
      |
      | MCP Protocol (stdio) / Direct calls
      v
+----------------------------------+
|  Python Driver (driver/)    |
|  +-- mcp/server.py   (FastMCP)  |
|  +-- cli/main.py     (Typer)    |
|  +-- connection/     (Socket)   |
+----------------------------------+
      |
      | TCP Socket (localhost:9876)
      | JSON-RPC 2.0
      v
+----------------------------------+
|  Ruby Runtime (runtime/)    |
|  +-- SketchUp Process           |
+----------------------------------+
```

## Project Structure

```
driver/
+-- src/supex_driver/
|   +-- __init__.py          # Package exports
|   +-- mcp/
|   |   +-- server.py        # FastMCP server, 14 tools + resources
|   |   +-- resources.py     # Documentation helpers
|   +-- cli/
|   |   +-- main.py          # Typer CLI, 14 commands
|   |   +-- docs.py          # Documentation browser
|   +-- connection/
|       +-- connection.py    # TCP socket client
|       +-- exceptions.py    # Error hierarchy
+-- resources/
|   +-- docs/
|       +-- INDEX.md         # Documentation index
|       +-- workflow.md      # AI workflow guidance
|       +-- best_practices.md # Modeling wisdom
|       +-- quick_reference.md # Quick reference
|       +-- api/             # Generated API docs (symlink)
+-- tests/                   # pytest suite
+-- pyproject.toml           # Package config
+-- README.md
```

## MCP Resources

Documentation is exposed via MCP resources (readable by Claude Code):

| Resource URI | Description |
|--------------|-------------|
| `supex://docs/INDEX` | Documentation overview - start here |
| `supex://docs/workflow` | Complete workflow guide for Ruby scripting |
| `supex://docs/best-practices` | Geometry lessons and common pitfalls |
| `supex://docs/quick-reference` | Quick reference for most used classes |
| `supex://docs/api/INDEX` | Lightweight API overview (~3k tokens) |
| `supex://docs/api/{namespace}/INDEX` | Namespace-specific index (Geom, Sketchup) |
| `supex://docs/api/{class_name}` | Class documentation using Ruby syntax (e.g., `Sketchup::Face`, `Geom::Point3d`) |
| `supex://docs/pages/{page_name}` | Tutorial pages (generating-geometry, importer-options, etc.) |

### Resource Files

| File | Resource | Contents |
|------|----------|----------|
| `resources/docs/INDEX.md` | `supex://docs/INDEX` | Quick start, resource overview |
| `resources/docs/workflow.md` | `supex://docs/workflow` | Execution patterns, code organization |
| `resources/docs/best_practices.md` | `supex://docs/best-practices` | Profile-first geometry, gotchas |
| `resources/docs/quick_reference.md` | `supex://docs/quick-reference` | Quick lookup reference |
| `resources/docs/api/` | `supex://docs/api/*` | Generated API documentation |

### When to Update What

| Document | Add |
|----------|-----|
| `workflow.md` | New tools, code patterns, API changes |
| `best_practices.md` | Modeling lessons, gotchas, tips |
| `INDEX.md` | New resources, navigation changes |

## Development

### Setup

```bash
cd driver
uv sync --dev
```

### Commands

```bash
# Linting
uv run ruff check src/ tests/

# Formatting
uv run ruff format src/ tests/

# Type checking
uv run mypy src/

# Tests
uv run pytest tests/ -v
```

### Entry Points

| Script | Purpose |
|--------|---------|
| `./mcp` | MCP server (for Claude Code) |
| `./supex` | CLI interface |
| `supex-mcp` | Direct MCP entry point |
| `supex` | Direct CLI entry point |

### Testing Connection

```bash
# Quick connection test
./supex status

# Or programmatically
uv run python -c "
from supex_driver.connection import get_sketchup_connection
conn = get_sketchup_connection()
print(conn.send_command('ping'))
"
```

## Error Handling

Exception hierarchy:
- `SketchUpError` - Base exception
- `SketchUpConnectionError` - Connection failures
- `SketchUpTimeoutError` - Timeout errors
- `SketchUpProtocolError` - JSON/protocol errors

### Logging

MCP server logs to `~/.supex/logs/` (configurable via `SUPEX_LOG_DIR`):
- `stdout.log` - Standard output
- `stderr.log` - Errors and warnings
- `cli.log` - CLI-specific logs
