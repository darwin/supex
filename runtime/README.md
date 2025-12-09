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
| `get_selection()` | Currently selected entities |
| `get_layers()` | All layers/tags |
| `get_materials()` | All materials with colors |
| `get_camera_info()` | Camera position and settings |
| `take_screenshot(path?)` | Save view to file |
| `take_batch_screenshots(params)` | Multiple screenshots with camera control |
| `open_model(path)` | Open .skp file |
| `save_model(path?)` | Save model |
| `export_scene(format)` | Export: skp, obj, stl, png, jpg |
| `console_capture_status()` | Console capture info |

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
| Export | SKP, OBJ, STL, PNG, JPG export |
| ConsoleCapture | stdout/stderr redirection to log files |
| Utils | Logging, JSON-RPC response helpers, entity utilities |

## Usage

### Starting the Server

**Automatic**: Server starts when SketchUp loads the extension.

**Manual**: `Extensions > Supex > Server Status`

**Menu Options**:
- Server Status - Show current status
- Stop Server - Stop TCP server
- Restart Server - Restart TCP server
- Reload Extension - Hot reload code changes
- Show Console - Open Ruby console

### Default Configuration

- **Host**: 127.0.0.1
- **Port**: 9876 (Bridge), 4433 (REPL)
- **Protocol**: JSON-RPC 2.0

## REPL Server

The REPL server provides interactive Ruby development in SketchUp context.

### Connecting

Use the REPL client script:

```bash
cd runtime/src
./repl.rb              # Simple line-by-line mode
./repl.rb --pry        # Pry mode (RubyMine compatible)
./repl.rb -p 4433      # Connect to specific port
```

### RubyMine Integration

Load via Pry for IDE integration:

```bash
pry -r ./repl.rb
```

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
| `SUPEX_REPL_HOST` | `127.0.0.1` | REPL server host |
| `SUPEX_REPL_DISABLED` | not set | Set to `1` to disable REPL server |
| `SUPEX_REPL_BUFFER_MS` | `50` | Input buffer timeout for IDE paste detection |

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
| `bundle exec rake build` | Build .rbz package |
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
2. **MCP Tool**: Call `reload_extension()` via Python driver
3. **Ruby Console**: `SupexRuntime::Main.reload_extension`

### Debugging

Console output is logged to `.tmp/sketchup_console.log`:

```ruby
# Check capture status
SupexRuntime::Main.server_status

# View log path
# Log location: <repo>/.tmp/sketchup_console.log
```

## Requirements

- **SketchUp 2026**: Latest official version only
- **Bundler**: For dependency management (development only)