# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Workflow

**General Critical Guidelines:**

- **NEVER bump version numbers** unless explicitly asked by the user - version changes should be intentional and controlled
- **NEVER commit changes** unless explicitly asked by the user - all git commits should be intentional and reviewed
- **NEVER read files in git-ignored folders** unless explicitly asked by the user - these often contain sensitive data or temporary files
- **NEVER use emojis in documentation** - documentation should be professional and emoji-free; use clear section headings instead
- **Use `git ls-tree -r HEAD` to find project files** - do not look at other files unless explicitly asked by the user
- **Use portable shebangs in all executable scripts** - use `#!/usr/bin/env bash` for bash scripts, `#!/usr/bin/env python3` for Python, etc. This ensures scripts work across different systems where interpreters may be installed in different locations

## SketchUp Modeling Workflow

**Project-Based Development**: Supex follows a project-based workflow similar to web development:

### When users ask for SketchUp modeling help:

1. **Create Ruby scripts in the project** - e.g., `scripts/create_table.rb`
   - Write clean, well-commented Ruby code
   - Follow guidelines in `src/driver/prompts/sketchup_workflow.md`
   - Use proper SketchUp API patterns

2. **Execute scripts with `eval_ruby_file`** - Run the Ruby file in SketchUp context
   - Provides proper error reporting with file context
   - Line numbers and stack traces work correctly

3. **Use introspection tools to verify results:**
   - `get_model_info()` - Check entity counts and model state
   - `take_screenshot()` - Save screenshot to disk (returns path only!)
     - **IMPORTANT**: Tool returns file path, not image data (~200 tokens vs 21k)
     - Only use Read tool on screenshot path if user explicitly asks to see it
     - Don't automatically read screenshots - saves massive context
   - `get_selection()` - Verify what's selected
   - `list_entities()` - Inspect created geometry

4. **Iterate based on user feedback** - Edit the Ruby file and re-run
   - All scripts are in the project (git trackable!)
   - User can edit scripts in their IDE
   - Full RuboCop and syntax highlighting support

**Model files**: SketchUp models (.skp) should be in the project root or a `models/` directory.

**Script organization**:
- `scripts/` - Main modeling scripts
- `scripts/utilities/` - Reusable helper functions
- `scripts/components/` - Component definitions

**Best practices from sketchup_workflow.md**:
- Always use metric units
- Start operations with `model.start_operation`
- Organize in groups/components
- Use descriptive names

## Project Overview

This is a production-ready SketchUp automation platform using Model Context Protocol (MCP). The project structure:

```
supex/
├── src/
│   ├── driver/                # Python MCP driver + CLI
│   │   └── src/supex_driver/
│   │       ├── adapter/       # SketchupRuntime connection
│   │       ├── mcp/           # MCP server
│   │       └── cli/           # CLI interface
│   └── runtime/               # Ruby SketchUp extension
│       ├── supex_runtime.rb
│       └── supex_runtime/
├── scripts/                   # Development automation scripts
└── inspiration/               # Reference implementations
```

## Architecture

The project follows the MCP (Model Context Protocol) pattern with:
- **Python MCP Driver**: Handles external communication and provides AI-accessible tools
- **Ruby SketchUp Runtime**: Runs inside SketchUp and executes actual geometry operations
- **Socket Communication**: The Python driver communicates with the Ruby runtime via TCP sockets

**Current Implementation:**
- `src/driver/` - Python MCP driver with FastMCP framework
- `src/runtime/` - Ruby SketchUp extension with modular architecture
- Socket communication on localhost:9876 (default port)
- Ruby injection via `-RubyStartup` for seamless development workflow

## Development Commands

### SketchUp Launcher System

The repository includes a streamlined launcher system for SketchUp development:

```bash
# Launch SketchUp with direct source deployment
./scripts/launch-sketchup.sh

# Manual extension building (for production .rbz)
cd src/runtime
bundle exec rake build
```

**SketchUp Launcher Features:**
- Automatically detects SketchUp installation (2020-2024)
- Deploys Ruby sources directly (no .rbz building required)
- SketchUp loads sources from development directory
- Extension can reload itself during development
- Graceful shutdown with AppleScript integration
- Comprehensive logging and error handling

**Development Workflow:**
1. Edit Ruby source files in `src/runtime/supex_runtime/`
2. Reload extension: `./supex reload`
3. Changes are picked up immediately without restarting SketchUp

### Python MCP Driver (src/driver/)
```bash
# Run the MCP server
./mcp

# Run the CLI
./supex --help
./supex status
./supex info

# Run tests
cd src/driver
uv run pytest tests/
```

## Key Files

- `src/driver/src/supex_driver/mcp/server.py` - Main MCP server implementation
- `src/driver/src/supex_driver/adapter/connection.py` - SketchupRuntime adapter
- `src/driver/src/supex_driver/cli/main.py` - CLI implementation
- `src/runtime/supex_runtime/main.rb` - SketchUp extension entry point
- `src/runtime/supex_runtime/` - Modular Ruby extension components
- `scripts/launch-sketchup.sh` - Main development launcher script

## Development Notes

- The SketchUp extension communicates via socket server (default port 9876)
- Ruby code is executed within SketchUp's context using `eval_ruby` tool
- The MCP driver handles connection management with automatic reconnection
- Both Python and Ruby components are required for full functionality
- Ruby injection system enables direct source loading without file deployment
- Extension supports live reloading during development
- Comprehensive logging and error handling throughout the system
