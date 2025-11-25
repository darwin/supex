# Supex Driver

Python MCP server and CLI for SketchUp automation. Enables AI agents and command-line tools to execute Ruby code in SketchUp through the Model Context Protocol.

## Overview

Supex Driver is part of the Supex platform - a bridge between AI agents and SketchUp. It provides:

- **MCP Server**: 14 tools for AI agents via Model Context Protocol
- **CLI**: 14 commands for direct terminal interaction
- **Connection Layer**: TCP/JSON-RPC client for SketchUp runtime

## MCP Tools

### Execution

| Tool | Description |
|------|-------------|
| `eval_ruby(code)` | Execute Ruby code directly |
| `eval_ruby_file(path)` | Execute Ruby script from file (preferred) |
| `reload_extension()` | Reload runtime without restarting SketchUp |

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
|  Python Driver (src/driver/)    |
|  +-- mcp/server.py   (FastMCP)  |
|  +-- cli/main.py     (Typer)    |
|  +-- connection/     (Socket)   |
+----------------------------------+
      |
      | TCP Socket (localhost:9876)
      | JSON-RPC 2.0
      v
+----------------------------------+
|  Ruby Runtime (src/runtime/)    |
|  +-- SketchUp Process           |
+----------------------------------+
```

## Project Structure

```
src/driver/
+-- src/supex_driver/
|   +-- __init__.py          # Package exports
|   +-- mcp/
|   |   +-- server.py        # FastMCP server, 14 tools
|   +-- cli/
|   |   +-- main.py          # Typer CLI, 14 commands
|   +-- connection/
|       +-- connection.py    # TCP socket client
|       +-- exceptions.py    # Error hierarchy
+-- prompts/
|   +-- sketchup_workflow.md # AI code guidance
+-- resources/
|   +-- best_practices.md    # Modeling wisdom
+-- tests/                   # pytest suite
+-- pyproject.toml           # Package config
+-- README.md
```

## AI Guidance Documents

### Workflow Prompt (`prompts/sketchup_workflow.md`)

Loaded as MCP prompt `ruby_scripting_strategy`. Contains:
- Core workflow (write, execute, verify, iterate)
- Execution rules (eval_ruby vs eval_ruby_file)
- Code patterns (transactions, modules, idempotence)
- Units and coordinate system
- Tools reference

### Best Practices (`resources/best_practices.md`)

Available as MCP resource `supex://docs/best-practices`. Contains:
- Profile-first geometry
- Pushpull direction gotchas
- Edge treatment
- Common pitfalls

### When to Update What

| Document | Add |
|----------|-----|
| Workflow | New tools, code patterns, API changes |
| Best Practices | Modeling lessons, gotchas, tips |

## Development

### Setup

```bash
cd src/driver
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

- MCP server logs: `.tmp/supex-mcp.log`
- Extension logs: `~/.supex/logs/`
