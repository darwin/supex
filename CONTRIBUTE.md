# Contributing to Supex

Thank you for your interest in contributing to Supex! This guide will help you set up your development environment and understand the contribution workflow.

## Development Prerequisites

### Required Tools

- **SketchUp 2020+** - Any recent version with Ruby API
- **Ruby 3.4.7** - Managed via mise for extension development
- **Python 3.14** - Latest Python with UV package manager
- **mise** - Multi-language version management
- **git** - Version control

### Why These Versions?

**Ruby 3.4.7:**
- Latest features and performance improvements
- Required for extension development and testing
- Managed via mise for environment isolation

**Python 3.14:**
- Enhanced performance with improved bytecode interpreter
- Better error messages and diagnostics
- Enhanced type annotations for better mypy support
- Latest security patches

## Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/supex.git
cd supex
```

### 2. Setup Ruby Environment

```bash
# Install Ruby via mise
mise install

# Install Ruby dependencies
cd src/runtime
bundle install
```

### 3. Setup Python Environment

```bash
cd src/driver
uv sync --dev
```

### 4. Launch Development Environment

```bash
# From repository root
./scripts/launch-sketchup.sh

# For verbose output
SUPEX_VERBOSE=1 ./scripts/launch-sketchup.sh
```

## Project Structure

```
supex/
├── mcp                             # MCP server wrapper script
├── supex                           # CLI wrapper script
├── scripts/
│   ├── launch-sketchup.sh          # Main SketchUp launcher
│   └── helpers/                    # Helper scripts
│       └── shutdown-sketchup.applescript  # Graceful SketchUp shutdown
├── src/
│   ├── driver/                     # Python MCP server
│   │   ├── src/supex_driver/      # Server implementation
│   │   ├── prompts/               # AI guidance prompts
│   │   ├── resources/             # Resources and best practices
│   │   ├── examples/              # Usage examples
│   │   ├── tests/                 # Driver tests
│   │   └── pyproject.toml         # UV package config
│   └── runtime/                    # Ruby SketchUp extension
│       ├── injector.rb            # Ruby injection script
│       ├── supex_runtime.rb       # Extension registration
│       ├── supex_runtime/         # Modular Ruby sources
│       ├── Gemfile                # Ruby dependencies
│       └── Rakefile               # Build automation
├── tests/                          # End-to-end tests
│   ├── e2e/                       # E2E test suite
│   ├── helpers/                   # Test helpers
│   └── data/                      # Test data
├── examples/
│   └── simple-table/               # Example project demonstrating workflow
├── ARCHITECTURE.md                 # Technical architecture documentation
├── CLAUDE.md                       # AI development guidelines
├── CONTRIBUTE.md                   # This file
└── README.md                       # User-facing documentation
```

## Development Workflow

### Ruby Extension Development

The Ruby extension can be developed with live reloading:

```bash
# 1. Edit Ruby source files in src/runtime/supex_runtime/

# 2. Reload extension without restarting SketchUp
./supex reload

# With custom host/port
./supex reload --host 127.0.0.1 --port 9876
```

**Extension Development Cycle:**
1. Edit Ruby extension sources in `src/runtime/supex_runtime/`
2. Reload extension via CLI: `./supex reload`
3. Test changes immediately without SketchUp restart
4. Iterate rapidly with instant feedback

### Ruby Extension Build System

```bash
cd src/runtime

# Install dependencies
bundle install

# Run code linting
bundle exec rubocop

# Build production .rbz package
bundle exec rake build
```

### Python MCP Server Development

```bash
cd src/driver

# Run tests
uv run pytest tests/ -v

# Code quality checks
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

## Technical Architecture

### Ruby Injection System

The development environment uses a direct Ruby injection system:

- **Direct Loading**: Sources loaded via `$LOAD_PATH` manipulation
- **No File Copying**: Extension sources remain in development directory
- **Injector Script**: `injector.rb` handles Ruby environment setup
- **SketchUp Integration**: Uses `-RubyStartup` flag for seamless injection
- **Live Reloading**: Extension can reload itself during development

### SketchUp Launcher Features

The `./scripts/launch-sketchup.sh` launcher provides:

- Automatically detects SketchUp installation (2020-2024)
- Validates extension sources before launch
- Deploys Ruby sources directly (no .rbz building required)
- SketchUp loads sources from development directory
- Graceful shutdown with AppleScript integration
- Comprehensive logging and error handling

### Modern Ruby Development

- **mise Isolation**: Ruby 3.4.7 environment isolation
- **Modular Architecture**: Clean separation of concerns across focused modules
- **Build Automation**: Comprehensive Rakefile with packaging, linting, documentation
- **Code Quality**: RuboCop integration with SketchUp-specific rules

### Python MCP Server

- **FastMCP Framework**: Modern async MCP patterns with lifecycle management
- **UV Package Management**: Fast dependency resolution and development workflow
- **Comprehensive Testing**: Full test suite with async support
- **Type Safety**: Complete type annotations with mypy validation
- **Socket Adapter**: TCP communication with SketchUp runtime on localhost:9876

### Communication Architecture

The project follows the MCP (Model Context Protocol) pattern:

- **Python MCP Driver**: Handles external communication and provides AI-accessible tools
- **Ruby SketchUp Runtime**: Runs inside SketchUp and executes actual geometry operations
- **Socket Communication**: The Python driver communicates with the Ruby runtime via TCP sockets (localhost:9876)
- **JSON-RPC 2.0**: Protocol for bidirectional communication
- **Automatic Reconnection**: Driver handles connection management with health checking

## Code Quality Standards

### Ruby Code Standards

- **RuboCop**: All Ruby code must pass RuboCop linting
- **SketchUp API Patterns**: Follow SketchUp best practices (operations, groups, error handling)
- **Portable Shebangs**: Use `#!/usr/bin/env ruby` in executable scripts

### Python Code Standards

- **Ruff**: All Python code must pass Ruff formatting and linting
- **mypy**: Complete type annotations with mypy validation
- **pytest**: All new features require test coverage
- **Portable Shebangs**: Use `#!/usr/bin/env python3` in executable scripts

### Git Commit Standards

- **Conventional Commits**: Use descriptive commit messages
- **Detailed Descriptions**: Explain the "why" not just the "what"
- **No Version Bumps**: Version changes should be intentional and controlled
- **Meaningful Commits**: Each commit should be a logical unit of work

## Testing Guidelines

### Python Tests

```bash
cd src/driver
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_connection.py -v

# Run with coverage
uv run pytest tests/ --cov=src/supex_driver
```

### End-to-End Tests

```bash
cd tests/e2e
# E2E testing infrastructure is in development
```

### Manual Testing

1. Launch SketchUp with extension: `./scripts/launch-sketchup.sh`
2. Start MCP server manually (for debugging): `./mcp`
3. Test CLI commands: `./supex status`, `./supex info`
4. Test MCP tools via Claude Code or MCP client

## Contribution Process

### 1. Fork and Clone

```bash
git clone https://github.com/yourusername/supex.git
cd supex
git remote add upstream https://github.com/original/supex.git
```

### 2. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 3. Make Your Changes

- Follow code quality standards
- Add tests for new functionality
- Update documentation as needed
- Run linters and tests before committing

### 4. Commit Your Changes

```bash
git add .
git commit -m "Add feature: brief description

Detailed explanation of what changed and why.
"
```

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear description of changes
- Reference to any related issues
- Screenshots/examples if applicable

### 6. Code Review

- Respond to reviewer feedback
- Make requested changes
- Keep the PR updated with main branch

## Development Tips

### SketchUp Extension Debugging

- Use `puts` statements for logging (output appears in Ruby Console)
- Check `.tmp/supex-runtime.log` for extension logs
- Use `./supex reload` frequently during development
- Test with different SketchUp versions if possible

### Python Server Debugging

- MCP server logs go to `.tmp/supex-mcp.log`
- Use `./mcp` manually for direct testing
- Check socket connection with `./supex status`
- Use pytest with `-v` flag for detailed test output

### Common Issues

**Extension Not Loading:**
- Check Ruby syntax errors in extension files
- Verify `injector.rb` is being executed
- Look for errors in SketchUp Ruby Console

**Socket Connection Failed:**
- Ensure SketchUp is running with extension loaded
- Check port 9876 is not in use by another process
- Verify firewall settings allow localhost connections

**Tests Failing:**
- Run `uv sync --dev` to ensure dependencies are current
- Check Python version is 3.14+
- Verify Ruby environment with `mise current`

## Getting Help

- **Issues**: Report bugs and request features via GitHub issues
- **Discussions**: Join discussions for questions and ideas
- **Documentation**: Check ARCHITECTURE.md for technical details
- **Examples**: See examples/simple-table/ for working code patterns

Thank you for contributing to Supex!
