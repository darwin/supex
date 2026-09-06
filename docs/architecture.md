# Architecture Overview

## System Design

For authoritative command/tool/env lists, use:

- [CLI Reference](cli.md)
- [MCP Reference](agents/guide/mcp.md)
- [Configuration](configuration.md)
- [Protocol](protocol.md)

Supex implements a multi-process architecture for robust SketchUp automation:

```
                                                          ┌──────────────────────────────────┐
┌──────────────────┐                                      │          SketchUp                │
│  REPL            │─────── :4433 TCP JSON-RPC ──────────▶│                                  │
│  ./repl          │                                      │   ┌────────────────────────┐     │
└──────────────────┘                                      │   │  Supex Runtime  :9876  │     │
                                                          │   │  REPL Server    :4433  │     │
┌──────────────────┐        ┌──────────────────────┐      │   └────────────────────────┘     │
│  AI Agent        │──MCP──▶│                      │      │   ┌──────────┐ ┌─────────────┐  │
│  Claude          │        │      Driver          ├──────┤   │  StdLib  │ │ SketchUp API│  │
└──────────────────┘        │      Python          │ :9876│   └──────────┘ └─────────────┘  │
                     ┌─────▶│      ./mcp           │ TCP  └──────────────────────────────────┘
┌──────────────────┐ │      │                      │ JSON-RPC        ▲
│  CLI             │─┘      │                      │                 │  DAE file
│  ./supex         │        │                      │                 │  (filesystem)
└──────────────────┘        │                      ├── :9877 TCP ──▶┌┴─────────────────────┐
                            │                      │   JSON-RPC     │  VCAD Sidecar        │
                            │                      │                │  Rust                 │
                            │                      │                └───────────────────────┘
                            │                      │
                            │                      ├── :9878 WS ──▶┌───────────────────────┐
                            │                      │                │  VCAD Viewer          │
                            └──────────────────────┘                │  Tauri app            │
                                                                    └───────────────────────┘
```

The Driver is the central hub: CLI and MCP are two entry points into the same Python process. The Driver connects to SketchUp (:9876), the VCAD Sidecar (:9877), and relays mesh data to the VCAD Viewer via WebSocket (:9878). The REPL client connects directly to SketchUp's REPL server (:4433), bypassing the Driver. Mesh exchange between Sidecar and SketchUp happens via the filesystem (DAE files).

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
│   ├── viewer/                # Tauri BRep viewer app
│   └── vendor/                # Git submodules: vcad kernel, loon language, tang autodiff
├── stdlib/                    # Ruby standard library helpers
├── mock/                      # Headless SketchUp API mock (Ruby) for tests without SketchUp
├── devtools/                  # Developer tooling
│   ├── ci/                    # Dockerfile for the CI test image
│   ├── docgen/                # SketchUp API documentation generator
│   └── radar/                 # Log aggregator TUI
├── scripts/                   # Development automation
├── tests/                     # E2E and integration tests
│   ├── e2e/                   # End-to-end tests
│   ├── snippets/              # Ruby test snippets
│   └── helpers/               # Test utilities
├── examples/                  # Example projects (checked out from orphan branches)
└── docs/                      # Documentation
```

## Component Architecture

### Python Driver (`driver/`)

**Framework**: MCP Python SDK `MCPServer` (MCP server) + Typer (CLI)
**Purpose**: MCP protocol handling, tool interface, and standalone CLI

The driver serves two roles: as an MCP server for AI agents, and as a CLI (`./supex`) for direct human use. Both share the same connection layer and tool implementations.

**Key Components**:
- `src/supex_driver/mcp/mcp_server.py` - MCP server with tool definitions
- `src/supex_driver/cli/main.py` - Typer CLI application
- `src/supex_driver/__main__.py` - Entry point and startup configuration
- Complete type annotations and mypy validation

Tool catalogs are maintained in dedicated reference docs:

- [CLI Reference](cli.md)
- [MCP Reference](agents/guide/mcp.md)
- [VCAD Integration](vcad.md)

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

For environment variables and defaults, see [Configuration](configuration.md).

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

VCAD extends supex with a parametric modeling pipeline. The agent writes `.cmp.oo` source files in Loon (a Lisp with algebraic data types), and the sidecar evaluates them to produce BRep geometry that is imported into SketchUp as components.

**Evaluation Pipeline**:
```
.cmp.oo source → Loon parse → Value::Adt tree → vcad_ir::Document
    → vcad_kernel::Solid (BRep) → TriangleMesh → DAE → SketchUp import
```

**Sidecar** (`vcad/sidecar/`, Rust):
- TCP JSON-RPC server on port 9877
- Loon interpreter with VCAD standard library
- BRep kernel (primitives, booleans, transforms, fillets, patterns)
- DAE mesh export
- Filesystem watcher for `.cmp.oo` and `.oo` module changes
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

For the complete VCAD tool inventory (including diagnostics/viewer tools), see:

- [MCP Reference](agents/guide/mcp.md)
- [VCAD Integration](vcad.md)

## Communication Protocol

**Transport**: TCP Sockets and WebSocket
**Protocol**: JSON-RPC 2.0
**Serialization**: JSON with UTF-8 encoding

| Port | Transport | Direction | Purpose |
|------|-----------|-----------|---------|
| 4433 | TCP | REPL client ↔ SketchUp | Ruby REPL (interactive eval in TOPLEVEL_BINDING) |
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
**Ruby**: Ruby 3.2.2 (see `.ruby-version`), Bundler dependency management. The version is dictated by the interpreter embedded in SketchUp 2025/2026; it is past upstream end-of-life, but bumping it is not possible until SketchUp bundles a newer Ruby
**Quality**: Ruff (Python), RuboCop (Ruby), MyPy type checking
**Testing**: pytest (Python), Minitest (Ruby)

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
./test
```

If you have [just](https://github.com/casey/just) installed:

```bash
just test       # All tests
just test-e2e   # All tests including E2E
just lint       # All linters
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
- Unit tests with Minitest framework
- Code style with RuboCop and SketchUp-specific rules

## Security Considerations

**Network Security**:
- Localhost-only binding by default (no external network exposure)
- Optional authentication via `SUPEX_AUTH_TOKEN` (SketchUp bridge)
- VCAD sidecar requires `SUPEX_VCAD_AUTH_TOKEN` for non-loopback binds (`SUPEX_VCAD_ALLOW_REMOTE=1`)
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
