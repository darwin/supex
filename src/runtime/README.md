# Supex Runtime: Ruby SketchUp Extension

A modern, modular Ruby extension for SketchUp that provides MCP (Model Context Protocol) integration for AI-driven 3D modeling and design automation.

## Features

### Core Architecture
- **Modular Design**: Clean separation of concerns across focused modules
- **Ruby 3.4.7**: Latest Ruby with performance improvements and enhanced features
- **Live Reloading**: Change code without restarting SketchUp
- **Comprehensive Logging**: Detailed progress tracking and error reporting

### 3D Modeling Capabilities
- **Session Management**: Organized file-based Ruby scripting with timestamped sessions
- **Direct Ruby Execution**: Execute Ruby code directly in SketchUp context
- **Console Capture**: All output logged with timestamps for debugging
- **File-based Workflow**: Create and execute Ruby scripts from organized sessions

### Advanced Features
- **Export Formats**: SKP, OBJ, STL, PNG, JPG support
- **Ruby Code Evaluation**: Direct SketchUp API access for complex operations
- **Strategic Guidance**: Built-in 3D modeling expertise integration
- **Component Naming**: Organized model structure with descriptive names

## Architecture

The extension is organized into focused modules:

```
supex_runtime/
├── version.rb         # Version and metadata management
├── utils.rb           # Common utilities and helpers
├── console_capture.rb # Console output logging and monitoring
├── session_manager.rb # File-based Ruby scripting sessions
├── export.rb          # Multi-format export functionality
├── server.rb          # TCP server and JSON-RPC handling
└── main.rb            # Orchestration and menu integration
```

## Requirements

- **SketchUp 2019+**: Any version from 2019 onwards with Ruby API support
- **Ruby 3.4.7**: Managed via mise for environment isolation
- **Bundler**: Dependency management

## Installation

### Recommended: Use Launcher Script

From the repository root:

```bash
./launch-sketchup.sh
```

This automatically handles Ruby injection and extension loading.

### Manual Installation

1. **Setup Ruby Environment**:
   ```bash
   mise install
   ```

2. **Install Dependencies**:
   ```bash
   bundle install
   ```

3. **Build Extension Package**:
   ```bash
   bundle exec rake build
   ```

4. **Install to SketchUp**:
   ```bash
   bundle exec rake install
   ```

## Development Workflow

### Live Development Cycle

1. **Edit** Ruby source files in `supex_runtime/`
2. **Reload** extension via one of these methods:
   - **SketchUp Menu**: `Extensions > Supex Runtime > Reload Extension`
   - **MCP Tool**: Call `reload_extension` via MCP server
   - **Ruby Console**: `SupexRuntime::Main.reload_extension`
3. **Test** changes immediately without SketchUp restart
4. **Iterate** rapidly with instant feedback

### Ruby Injection System

The extension uses Ruby injection for optimal development experience:

- **Direct Source Loading**: Extension loads from development directory
- **No File Copying**: Sources remain in place, no deployment needed
- **Environment Setup**: Proper Ruby environment configuration via `injector.rb`
- **Auto-start**: Extension automatically starts server on load

### Build Commands

```bash
# Install dependencies
bundle install

# Build .rbz package for production
bundle exec rake build

# Install extension to SketchUp
bundle exec rake install

# Run code linting
bundle exec rubocop

# Auto-fix linting issues
bundle exec rubocop -A

# Generate documentation
bundle exec yard

# Run tests
bundle exec rake test
```

## Usage

### Starting the Extension

**With Launcher (Recommended)**:
The launcher script automatically loads and starts the extension.

**Manual Method**:
1. Open SketchUp
2. Go to `Extensions > Supex Runtime > Start Server`
3. Extension starts listening on localhost:9876

### Core Operations

The extension provides these capabilities via MCP:

#### Session Management
```ruby
# Create a new modeling session
create_session("table-design")

# Create a Ruby script in the session
create_ruby_file(session_path, "table-legs", ruby_code)
```

#### Ruby Code Execution
```ruby
# Execute Ruby code directly
eval_ruby("model = Sketchup.active_model")

# Execute Ruby file from session
eval_ruby_file("/path/to/script.rb")
```

#### Export and Evaluation
```ruby
# Export scene
export_scene("skp")

# Execute Ruby code
eval_ruby("puts 'Hello from SketchUp!'")
```

## Configuration

### Socket Communication

Default configuration:
- **Host**: localhost
- **Port**: 9876
- **Protocol**: JSON-RPC 2.0

### Extension Settings

Configure via SketchUp menu: `Extensions > Supex Runtime > Settings`

Options include:
- Server host and port configuration
- Logging levels and output preferences
- Auto-start behavior
- Development mode toggles

## Testing

### Running Tests

```bash
# Run all tests
bundle exec rake test

# Run specific test file
bundle exec ruby tests/test_geometry.rb

# Run with verbose output
bundle exec rake test TESTOPTS="-v"
```

### Test Structure

Tests are organized to cover the main functionality of each module. The test suite validates server operations, export functionality, and session management.

## Code Quality

### Linting with RuboCop

```bash
# Check code style
bundle exec rubocop

# Auto-fix issues
bundle exec rubocop -A

# Check specific files
bundle exec rubocop supex_runtime/geometry.rb
```

### Documentation with YARD

```bash
# Generate documentation
bundle exec yard

# View documentation
open doc/index.html

# Document coverage
bundle exec yard stats
```

## Debugging

### Logging

The extension provides comprehensive logging:

```ruby
# Console output is automatically captured to log files
# Check log file location
SupexRuntime::ConsoleCapture.log_file_path

# View current capture status
SupexRuntime::Main.console_capture_status
```

### Ruby Console

Access SketchUp's Ruby Console (`Window > Ruby Console`) for interactive debugging:

```ruby
# Check extension status
SupexRuntime::Main.server_running?

# Reload extension
SupexRuntime::Main.reload_extension

# Test server status
SupexRuntime::Main.server_status
```

## Contributing

### Development Setup

1. **Fork the repository**
2. **Setup Ruby environment**: `mise install`
3. **Install dependencies**: `bundle install`
4. **Launch development**: `./launch-sketchup.sh` (from repo root)
5. **Make changes** and test with live reloading

### Code Style

- Follow RuboCop configuration
- Add tests for new functionality
- Update documentation for API changes
- Use conventional commit messages

### Submitting Changes

1. Create a feature branch
2. Make your changes with tests
3. Run linting: `bundle exec rubocop`
4. Run tests: `bundle exec rake test`
5. Generate docs: `bundle exec yard`
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Architecture Notes

### Ruby Injection Benefits

- **Faster Development**: No build/deploy cycle
- **Live Debugging**: Change code and reload instantly
- **Source Control**: Work directly with source files
- **Environment Isolation**: mise ensures consistent Ruby version

### Module Responsibilities

- **Main**: Extension lifecycle, menu integration, coordination
- **Server**: TCP socket server, JSON-RPC protocol handling
- **ConsoleCapture**: Console output redirection and logging with timestamps
- **SessionManager**: File-based Ruby scripting sessions with organized structure
- **Export**: Multi-format export (SKP, OBJ, STL, PNG, JPG)
- **Utils**: Logging, error handling, common utilities
- **Version**: Metadata, version management, build information

### Performance Considerations

- **Lazy Loading**: Modules loaded on demand
- **Connection Pooling**: Efficient socket management
- **Error Boundaries**: Isolated error handling per operation
- **Memory Management**: Proper cleanup of SketchUp entities