# Architecture Overview

## System Design

Supex implements a dual-process architecture for robust SketchUp automation:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Claude Code   │────▶│   Python MCP     │────▶│   SketchUp      │
│   AI Client     │     │   Server         │     │   Extension     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                          │
                               │    TCP Socket            │
                               │    JSON-RPC 2.0          │
                               │    localhost:9876        │
                               └──────────────────────────┘
```

## Component Architecture

### Python MCP Server (`src/driver/`)

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
- **Visualization**: `take_screenshot` (saves to `.tmp/screenshots/`)
- **Model Management**: `open_model`, `save_model`, `export_scene` (SKP, OBJ, STL, PNG, JPG)
- **Connection Health**: `check_sketchup_status`, `console_capture_status`

### Ruby SketchUp Extension (`src/runtime/`)

**Architecture**: Modular Ruby extension with clean separation of concerns
**Purpose**: SketchUp Ruby API access and geometry operations

**Module Structure**:
```
supex_runtime/
├── main.rb            # Extension lifecycle and menu integration
├── server.rb          # TCP server and JSON-RPC protocol handling
├── export.rb          # Multi-format export functionality
├── utils.rb           # Logging, error handling, common utilities
├── console_capture.rb # Output capture and logging system
└── version.rb         # Version and metadata management
```

**Note**: Geometry and material operations are handled through direct Ruby code evaluation via `eval_ruby` and `eval_ruby_file` tools, providing unlimited flexibility for modeling operations.

## Communication Protocol

**Transport**: TCP Sockets (localhost:9876)
**Protocol**: JSON-RPC 2.0
**Serialization**: JSON with UTF-8 encoding

**Connection Management**:
- Automatic reconnection with exponential backoff
- Health checking with ping/pong heartbeat
- Graceful degradation and error recovery
- Connection pooling for efficiency

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
"/Applications/SketchUp 2024/SketchUp.app/Contents/MacOS/SketchUp" \
  -RubyStartup "/path/to/injector.rb"
```

### Modern Toolchain

**Python**: UV package management, Python 3.14+
**Ruby**: mise isolation, Ruby 3.4.7, Bundler dependency management
**Quality**: Ruff (Python), RuboCop (Ruby), MyPy type checking
**Testing**: pytest (Python), Test::Unit (Ruby)

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
- Localhost-only communication (no external network exposure)
- No authentication required (local development context)
- JSON-RPC 2.0 with structured message validation

**Code Execution**:
- Ruby code execution confined to SketchUp context
- No file system access outside SketchUp's normal permissions
- Extension permissions limited to SketchUp Ruby API

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