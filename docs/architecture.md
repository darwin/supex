# Architecture Overview

## System Design

Supex implements a multi-process architecture for robust SketchUp automation:

```
                                                  ┌─────────────────┐
                                           ┌─────▶│   Ruby REPL     │
                                           │      │   :4433 TCP     │
┌─────────────────┐     ┌──────────────────┤      └─────────────────┘
│   Claude Code   │────▶│   Python MCP     │      ┌─────────────────┐
│   AI Client     │     │   Driver         │─────▶│   SketchUp      │
└─────────────────┘     └──────────────────┘      │   Ruby Runtime  │
                          │    :9876 TCP JSON-RPC  │   :9876 TCP     │
                          │                        └─────────────────┘
                          │    :9877 TCP JSON-RPC
                          ▼
                  ┌──────────────────┐     ┌─────────────────┐
                  │   VCAD Rust      │     │   VCAD Viewer   │
                  │   Sidecar        │     │   (Tauri app)   │
                  └──────────────────┘     └─────────────────┘
                          │    :9878 WebSocket     │
                          └────────────────────────┘
```

## Project Structure

```
supex/
├── driver/                    # Python MCP Driver + CLI
│   ├── src/supex_driver/
│   │   ├── cli/               # CLI interface (status, eval)
│   │   ├── connection/        # Socket communication layer
│   │   │   ├── sketchup_*.py  # SketchUp TCP connection
│   │   │   ├── vcad_*.py      # VCAD sidecar connection, DAG, state, watcher
│   │   │   └── vcad_viewer_relay.py  # WebSocket bridge to viewer
│   │   └── mcp/               # MCP server and tool definitions
│   └── tests/                 # Unit tests
├── runtime/                   # Ruby SketchUp Extension
│   └── src/supex_runtime/
│       ├── bridge_server.rb   # TCP server (port 9876)
│       ├── tools.rb           # Core tool implementations
│       ├── vcad_tools.rb      # VCAD import resolution, mesh extraction
│       └── vcad_observer.rb   # VCAD node lifecycle observer
├── vcad/                      # VCAD parametric CAD subsystem
│   ├── sidecar/               # Rust sidecar (Loon eval + BRep kernel)
│   └── viewer/                # Tauri BRep viewer app
├── stdlib/                    # Ruby standard library helpers
├── scripts/                   # Development automation
├── tests/                     # E2E and integration tests
│   ├── e2e/                   # End-to-end tests
│   ├── snippets/              # Ruby test snippets
│   └── helpers/               # Test utilities
└── docs/                      # Documentation
```

## Component Architecture

### Python MCP Server (`driver/`)

**Framework**: FastMCP with async lifecycle management
**Purpose**: MCP protocol handling and tool interface provision

**Key Components**:
- `src/supex_driver/mcp/server.py` - Main MCP server implementation with tool definitions
- `src/supex_driver/__main__.py` - Entry point and startup configuration
- Modern async patterns with proper error handling
- Complete type annotations and mypy validation

**Tools Provided**:
- **Ruby Execution**: `eval_ruby`, `eval_ruby_file` (recommended)
- **Model Introspection**: `get_model_info`, `list_entities`, `get_selection`, `get_layers`, `get_materials`, `get_camera_info`
- **Visualization**: `take_screenshot`, `take_batch_screenshots` (multiple shots with camera control)
- **Model Management**: `open_model`, `save_model`, `export_scene` (SKP, OBJ, STL, PNG, JPG)
- **Connection Health**: `check_sketchup_status`, `console_capture_status`
- **VCAD**: `vcad_place`, `vcad_update`, `vcad_inspect`, `vcad_eval`, `vcad_export`, and more (see VCAD Subsystem below)

#### Connection Layer (`connection/`)

The connection module provides reliable communication with the SketchUp runtime:

**Architecture**:
- Thread-safe singleton pattern via `get_sketchup_connection()`
- TCP socket client with automatic lifecycle management
- JSON-RPC 2.0 message formatting and parsing

**Exception Types**:
- `SketchUpConnectionError` - Connection failures (socket errors, refused connections)
- `SketchUpTimeoutError` - Socket timeout exceeded
- `SketchUpProtocolError` - Invalid JSON response or protocol violation

**Reliability Features**:
- Automatic reconnection with retries (2 retries default)
- Configurable timeout (15s default)
- Hello handshake for connection identification
- Chunked response handling for large payloads

**Configuration** (environment variables):

| Variable             | Default     | Description                         |
|----------------------|-------------|-------------------------------------|
| `SUPEX_HOST`         | `localhost` | SketchUp runtime host               |
| `SUPEX_PORT`         | `9876`      | SketchUp runtime port               |
| `SUPEX_TIMEOUT`      | `15`        | Socket timeout in seconds           |
| `SUPEX_RETRIES`      | `2`         | Reconnection attempts               |
| `SUPEX_REPL_PORT`    | `4433`      | Ruby REPL server port               |
| `VCAD_HOST`          | `127.0.0.1` | VCAD sidecar host                  |
| `VCAD_PORT`          | `9877`      | VCAD sidecar port                  |
| `VCAD_AUTH_TOKEN`    | —           | Auth token (required for remote)    |
| `VCAD_ALLOW_REMOTE`  | —           | Set `1` to allow non-loopback bind  |

### Ruby SketchUp Extension (`runtime/`)

**Architecture**: Modular Ruby extension with clean separation of concerns
**Purpose**: SketchUp Ruby API access and geometry operations

**Module Structure**:
```
supex_runtime/
├── main.rb            # Extension lifecycle and menu integration
├── bridge_server.rb   # TCP server and JSON-RPC protocol handling (port 9876)
├── repl_server.rb     # Interactive REPL server via JSON-RPC (port 4433)
├── tools.rb           # Tool implementations (mixin for Server)
├── export.rb          # Multi-format export functionality
├── utils.rb           # Logging, error handling, common utilities
├── console_capture.rb # Output capture and logging system
└── version.rb         # Version and metadata management
```

**REPL Server**: A separate TCP server (default port 4433) provides interactive Ruby evaluation in `TOPLEVEL_BINDING` (same context as SketchUp's built-in console). Uses JSON-RPC 2.0 protocol with `hello` handshake and `eval` method. Non-blocking via SketchUp's UI timer. See [Interactive REPL](repl.md).

**Note**: Geometry and material operations are handled through direct Ruby code evaluation via `eval_ruby` and `eval_ruby_file` tools, providing unlimited flexibility for modeling operations.

### VCAD Subsystem (`vcad/`)

**Purpose**: Parametric BRep CAD engine for declarative geometry authoring in Loon

VCAD extends supex with a parametric modeling pipeline. The agent writes `.skp.oo` source files in Loon (a Lisp with algebraic data types), and the sidecar evaluates them to produce BRep geometry that is imported into SketchUp as components.

**Evaluation Pipeline**:
```
.skp.oo source → Loon parse → Value::Adt tree → vcad_ir::Document
    → vcad_kernel::Solid (BRep) → TriangleMesh → DAE → SketchUp import
```

**Sidecar** (`vcad/sidecar/`, Rust):
- TCP JSON-RPC server on port 9877
- Loon interpreter with VCAD standard library
- BRep kernel (primitives, booleans, transforms, fillets, patterns)
- DAE mesh export
- Filesystem watcher for `.skp.oo` and `.oo` module changes
- ADT cache for solid import composition
- Auth token support for non-loopback binds

**Driver Integration** (`connection/vcad_*.py`):
- `vcad_connection.py` — TCP client to sidecar with retry and auth
- `vcad_dag.py` — Dependency DAG for cascade updates
- `vcad_state.py` — Persistent node state (`.supex/vcad-state.json`)
- `vcad_file_watcher.py` — Reactive file change coordination
- `vcad_viewer_relay.py` — WebSocket bridge (:9878) to Tauri viewer

**Ruby Runtime** (`vcad_tools.rb`, `vcad_observer.rb`):
- DAE import into SketchUp as ComponentDefinition
- VCAD node attribute management (node_id, source_file, version)
- Import resolution: data extraction (dimensions, bbox, transform) and native solid mesh triangulation
- Entity lifecycle observer for node tracking

**Tools Provided**:
- **Placement**: `vcad_place`, `vcad_place_with_imports`
- **Updates**: `vcad_update`, `vcad_update_cascade`
- **Inspection**: `vcad_inspect`, `vcad_eval`, `vcad_list_nodes`
- **Export**: `vcad_export` (OBJ, STEP)
- **Batch editing**: `vcad_watch_pause`, `vcad_watch_resume`
- **Viewer**: `vcad_viewer_state`, `vcad_viewer_screenshot`, `vcad_viewer_focus`

See [VCAD Integration](vcad.md) for detailed documentation.

## Communication Protocol

**Transport**: TCP Sockets and WebSocket
**Protocol**: JSON-RPC 2.0
**Serialization**: JSON with UTF-8 encoding

| Port | Transport | Direction | Purpose |
|------|-----------|-----------|---------|
| 4433 | TCP | Driver ↔ SketchUp | Ruby REPL (interactive eval in TOPLEVEL_BINDING) |
| 9876 | TCP | Driver ↔ SketchUp | Ruby bridge (eval, introspection, import) |
| 9877 | TCP | Driver ↔ Sidecar | VCAD evaluation, import extraction |
| 9878 | WebSocket | Driver ↔ Viewer | BRep preview relay |

**Message Format**:

Request (Python to Ruby):
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {"name": "eval_ruby", "arguments": {"code": "..."}},
  "id": "request-123"
}
```

Response (Ruby to Python):
```json
{
  "jsonrpc": "2.0",
  "result": {"success": true, "result": "..."},
  "id": "request-123"
}
```

**Connection Management**:
- Automatic reconnection with retries
- Health checking with `ping` requests
- Graceful degradation and error recovery
- Thread-safe singleton pattern for connection management

## Development Features

### Ruby Injection System

**Mechanism**: Direct source loading via SketchUp's `-RubyStartup` flag
**Benefits**:
- No file deployment or copying required
- Sources remain in development directory
- Live reloading without SketchUp restart
- IDE-friendly development workflow

**Implementation**:
```bash
# Launch command
"/Applications/SketchUp 2026/SketchUp.app/Contents/MacOS/SketchUp" \
  -RubyStartup "/path/to/injector.rb"
```

### Modern Toolchain

**Python**: UV package management, Python 3.14+
**Ruby**: mise isolation, Ruby 3.2.2, Bundler dependency management
**Quality**: Ruff (Python), RuboCop (Ruby), MyPy type checking
**Testing**: pytest (Python), Test::Unit (Ruby)

## Testing Architecture

**Test Organization**:
```
tests/                     # Root test directory
├── e2e/                   # End-to-end tests (require running SketchUp)
├── snippets/              # Ruby code snippets for manual testing
├── helpers/               # Shared test utilities
└── conftest.py            # Pytest configuration and fixtures

driver/tests/              # Python unit tests (no SketchUp required)
```

**Test Categories**:

| Category | Location           | Requires SketchUp | Purpose                          |
|----------|--------------------|-------------------|----------------------------------|
| Unit     | `driver/tests/`    | No                | Python module isolation testing  |
| E2E      | `tests/e2e/`       | Yes               | Full system integration tests    |
| Snippets | `tests/snippets/`  | Yes               | Manual Ruby code verification    |

**Running Tests**:
```bash
# Python unit tests (no SketchUp needed)
cd driver && uv run pytest tests/

# E2E tests (SketchUp must be running)
./scripts/launch-tests.sh
```

## Quality Assurance

### Error Handling

**Multi-Layer Approach**:
1. **MCP Level**: Tool validation and protocol error handling
2. **Communication Level**: Socket errors, connection failures, timeouts
3. **Ruby Level**: SketchUp API errors, geometry operation failures
4. **User Level**: Friendly error messages with actionable guidance

### Logging System

**Features**:
- Color-coded output for different log levels
- Structured logging with context information
- Console capture for SketchUp Ruby output
- Configurable verbosity levels
- Log file persistence for debugging

### Testing Strategy

**Python Components**:
- Unit tests with pytest and async support
- Type checking with mypy
- Code quality with ruff linting and formatting

**Ruby Components**:
- Unit tests with Test::Unit framework
- Code style with RuboCop and SketchUp-specific rules

## Security Considerations

**Network Security**:
- Localhost-only binding by default (no external network exposure)
- Optional authentication via `SUPEX_AUTH_TOKEN` (SketchUp bridge)
- VCAD sidecar requires `VCAD_AUTH_TOKEN` for non-loopback binds (`VCAD_ALLOW_REMOTE=1`)
- JSON-RPC 2.0 with structured message validation

**Code Execution**:
- Ruby code execution confined to SketchUp context
- File path restrictions via `SUPEX_WORKSPACE` and `SUPEX_ALLOWED_ROOTS`
- VCAD sidecar enforces workspace path containment for source files
- Eval binding isolation between calls

See [Security](security.md) for detailed documentation.

## Performance Characteristics

**Startup Time**: ~2-3 seconds for full system initialization
**Communication Latency**: <10ms for typical Ruby operations
**Memory Usage**: ~50MB Python server, ~20MB Ruby extension
**Concurrent Operations**: Single-threaded Ruby execution (SketchUp limitation)

## Extensibility

**Adding New Tools**:
1. Define tool interface in Python MCP server
2. Implement functionality in appropriate Ruby module
3. Add communication protocol handling
4. Include tests and documentation

**Module Extension**:
- Ruby modules can be extended independently
- Clean interfaces allow for easy feature addition
- Modular architecture supports incremental development