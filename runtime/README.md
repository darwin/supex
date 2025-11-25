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
|  Ruby Runtime (runtime/)     |
|  +-- Server         (TCP/JSON)   |
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
+-- src/
    +-- injector.rb        # Ruby injection for dev
    +-- supex_runtime.rb   # Extension loader
    +-- supex_runtime/
        +-- main.rb        # Entry point, menu integration
        +-- server.rb      # TCP server, tool dispatch
        +-- export.rb      # Multi-format export
        +-- console_capture.rb # Output logging
        +-- utils.rb       # Helpers
        +-- version.rb     # Metadata
```

## Module Responsibilities

| Module | Purpose |
|--------|---------|
| Main | Extension lifecycle, SketchUp menu, server orchestration |
| Server | TCP socket server, JSON-RPC protocol, tool execution |
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
- **Port**: 9876
- **Protocol**: JSON-RPC 2.0

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

## Export Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| SketchUp | .skp | Native format |
| Wavefront | .obj | Triangulated, with textures |
| STL | .stl | For 3D printing |
| PNG | .png | Transparent background support |
| JPEG | .jpg | Compressed image |
