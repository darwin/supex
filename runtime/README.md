# Supex Runtime

Ruby SketchUp extension that exposes SketchUp API to external tools via TCP/JSON-RPC.

## Overview

Supex Runtime is part of the Supex platform:

- **TCP Server**: Listens on localhost:9876 for JSON-RPC requests
- **Tool Dispatch**: Routes requests to appropriate handlers
- **Console Capture**: Logs all Ruby output for debugging

## Available Tools

| Tool | Description |
|------|-------------|
| `ping` | Connection health check |
| `eval_ruby(code)` | Execute Ruby code directly |
| `eval_ruby_file(path)` | Execute Ruby script from file |
| `reload_extension()` | Hot reload without restart |
| `get_model_info()` | Entity counts, units, modified state |
| `list_entities(type)` | List geometry (all/faces/edges/groups/components) |
| `get_entity(entity_id)` | Full state of one entity: bounds, dimensions, layer, material, flags, transformation |
| `get_selection()` | Currently selected entities |
| `get_layers()` | All layers/tags |
| `get_materials()` | All materials with colors |
| `get_camera_info()` | Camera position and settings |
| `take_screenshot(width?, height?, transparent?, output_path?)` | Save view to PNG file |
| `take_batch_screenshots(params)` | Multiple screenshots with camera control |
| `open_model(path)` | Open .skp file |
| `save_model(path?)` | Save model |
| `export_scene(format)` | Export: skp, obj, stl, png, jpg, jpeg |
| `console_capture_status()` | Console capture info |

VCAD bridge tools (called by the driver's VCAD tools, not by agents directly):

| Tool | Description |
|------|-------------|
| `place_vcad_node(params)` | Import a DAE mesh as a component and store VCAD metadata |
| `update_vcad_node(params)` | Replace the geometry of an existing VCAD node |
| `list_vcad_nodes()` | List VCAD nodes in the model |
| `get_vcad_node(node_id)` | Return metadata of one VCAD node |
| `resolve_vcad_import(entity_id, extract)` | Extract dimensions, bbox, or transform from a SketchUp entity for a VCAD data import |
| `vcad.observer_start()` | Start the model change observer |
| `vcad.observer_stop()` | Stop the model change observer |
| `vcad.observer_poll()` | Drain queued model changes |

Relative paths passed to file tools resolve against the workspace sent in the `hello` handshake; `PathPolicy` rejects paths outside the workspace and `SUPEX_ALLOWED_ROOTS`.

## Architecture

```
Python Driver (MCP)
      |
      | TCP Socket (localhost:9876)
      | JSON-RPC 2.0
      v
+----------------------------------+
|  Ruby Runtime (runtime/)         |
|  +-- BridgeServer   (TCP/JSON)   |
|  +-- REPLServer     (TCP/JSON)   |
|  +-- Export         (formats)    |
|  +-- ConsoleCapture (logging)    |
|  +-- Utils          (helpers)    |
+----------------------------------+
      |
      v
  SketchUp Process (Ruby API)
```

## Project Structure

```
runtime/
+-- Rakefile               # Build tasks
+-- Gemfile                # Dependencies
+-- ide_stubs/             # IDE resolution shims
+-- src/
|   +-- injector.rb        # Ruby injection for dev
|   +-- repl.rb            # REPL client script
|   +-- supex_runtime.rb   # Extension loader
|   +-- supex_runtime/
|       +-- main.rb        # Entry point, menu integration
|       +-- bridge_server.rb # TCP server, tool dispatch
|       +-- tools.rb        # Core tool implementations
|       +-- batch_screenshot.rb # Multi-view screenshot batches
|       +-- vcad_tools.rb   # VCAD node import and lifecycle
|       +-- vcad_observer.rb # Model change queue for reactive VCAD
|       +-- path_policy.rb  # File path guardrail
|       +-- repl_server.rb # REPL server for interactive dev
|       +-- export.rb      # Multi-format export
|       +-- console_capture.rb # Output logging
|       +-- utils.rb       # Helpers
|       +-- version.rb     # Metadata
+-- test/
    +-- helpers/           # Test infrastructure
    +-- test_*.rb          # Test files
```

## Module Responsibilities

| Module | Purpose |
|--------|---------|
| Main | Extension lifecycle, SketchUp menu, server orchestration |
| BridgeServer | TCP socket server, JSON-RPC protocol, tool execution |
| REPLServer | Interactive Ruby development via TCP/JSON-RPC |
| Tools | Model introspection tools (entities, selection, camera, screenshot) |
| BatchScreenshot | Batch screenshots from standard or custom cameras with flicker-free camera restore and entity isolation |
| VCADTools | VCAD node management: mesh import, attribute storage, instance lifecycle |
| VcadObserverQueue / VcadModelObserver | Queue of model entity changes polled by the driver for reactive VCAD updates |
| PathPolicy | Path validation guardrail for file operations (`SUPEX_ALLOWED_ROOTS`) |
| Export | SKP, OBJ, STL, PNG, JPG/JPEG export |
| ConsoleCapture | stdout/stderr redirection to log files |
| Utils | Logging, JSON-RPC response helpers, entity utilities |

## Usage

### Starting the Server

**Automatic**: Server starts when SketchUp loads the extension.

**Manual**: `Extensions > Supex > Server Status`

**Menu Options**:
- Server Status - Show current status
- Stop All Servers - Stop both Bridge and REPL servers
- Restart All Servers - Restart both servers
- Start REPL / Stop REPL - Control REPL server separately
- Reload Extension - Hot reload code changes
- Show Console - Open Ruby console
- About - Show version information

### Default Configuration

- **Host**: 127.0.0.1
- **Port**: 9876 (Bridge), 4433 (REPL)
- **Protocol**: JSON-RPC 2.0

## REPL Server

The REPL server provides interactive Ruby development in SketchUp context.

### Connecting

Use the REPL client script:

```bash
./repl              # Simple line-by-line mode (from repo root)
./repl --pry        # Pry mode (RubyMine compatible)
./repl -p 4433      # Connect to specific port
```

### RubyMine Integration

Load via Pry for IDE integration:

```bash
pry -r /path/to/supex/runtime/src/repl.rb
```

See `docs/repl.md` for the RubyMine run configuration.

The client automatically patches Pry to send code to SketchUp.

### REPL Protocol

- **Method**: `hello` - Client handshake with PID for session management
- **Method**: `eval` - Execute Ruby code and return result

Each session creates a snippet directory in `.tmp/repl/` for debugging.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_VERBOSE` | `0` | Set to `1` to enable verbose logging |
| `SUPEX_NO_AUTOSTART` | not set | Define to disable automatic server start on extension load |
| `SUPEX_CHECK_INTERVAL` | `0.25` | Request check interval in seconds |
| `SUPEX_RESPONSE_DELAY` | `0` | Response delay in seconds (for debugging) |
| `SUPEX_REPL_PORT` | `4433` | REPL server port |
| `SUPEX_REPL_HOST` | `127.0.0.1` | REPL client default host |
| `SUPEX_REPL_DISABLED` | not set | Set to `1` to disable REPL server |
| `SUPEX_REPL_BUFFER_MS` | `50` | Input buffer timeout for IDE paste detection |
| `SUPEX_REPL_RETRIES` | `10` | REPL client connection retries with exponential backoff |
| `SUPEX_AUTH_TOKEN` | not set | Token clients must send in `hello`; also read by the REPL client |
| `SUPEX_ALLOW_REMOTE` | not set | Set to `1` to allow binding to a non-loopback address |
| `SUPEX_ALLOWED_ROOTS` | not set | Colon-separated extra roots allowed for file operations (`*` disables the check) |
| `SUPEX_STDLIB_PATH` | `../stdlib/src/supex_stdlib.rb` | Override path to the Supex stdlib entry file |
| `SUPEX_SILENT` | not set | Set to `1` to suppress console capture status messages |

## Protocol

All communication uses JSON-RPC 2.0 over TCP with newline-terminated messages.

### Connection Handshake

Clients must send a `hello` request before any other method:

```json
{"jsonrpc":"2.0","id":1,"method":"hello","params":{"name":"client","version":"1.0","agent":"mcp","pid":12345}}
```

After successful handshake, tool calls use the `tools/call` method.

## Development

### Setup

```bash
cd runtime
bundle install
```

### Commands

| Command | Description |
|---------|-------------|
| `bundle exec rake build` | Build .rbz package (bundles the stdlib so it works without a supex checkout) |
| `bundle exec rake install` | Install to SketchUp |
| `bundle exec rake clean` | Clean generated files |
| `bundle exec rubocop` | Code linting |
| `bundle exec rubocop -A` | Auto-fix lint issues |
| `bundle exec yard` | Generate API docs |
| `bundle exec rake test` | Run tests |

### Launch SketchUp (Development)

From repository root:

```bash
./scripts/launch-sketchup.sh
```

This uses Ruby injection to load sources directly from development directory.

### Live Reload

Change code and reload without restarting SketchUp:

1. **Menu**: `Extensions > Supex > Reload Extension`
2. **CLI**: `./supex reload` (calls the `reload_extension` bridge tool)
3. **Ruby Console**: `SupexRuntime::Main.reload_extension`

### Debugging

Console output is logged to `$SUPEX_WORKSPACE/.tmp/logs/runtime-console.log`:

```ruby
# Check capture status
SupexRuntime::Main.server_status

# View log path
# Log location: $SUPEX_WORKSPACE/.tmp/logs/runtime-console.log
```

## Requirements

- **SketchUp 2026**: Latest official version only
- **Bundler**: For dependency management (development only)
