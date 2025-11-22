# Supex: SketchUp Automation via Model Context Protocol

A production-ready SketchUp automation platform that enables AI agents to execute native SketchUp Ruby code through the Model Context Protocol (MCP). Built for professional 3D modeling workflows with direct API access, unlimited flexibility, and comprehensive development tools.

## Architecture Overview

Supex consists of two integrated components:

1. **Python MCP Server** (`src/driver/`) - Modern MCP server with FastMCP framework
2. **Ruby SketchUp Extension** (`src/runtime/`) - Native SketchUp extension with modular architecture

Communication happens via TCP sockets using JSON-RPC 2.0, providing direct access to SketchUp's Ruby API for AI agents.

## Key Features

### Ruby-First Approach
- **eval_ruby Tool**: Primary interface for all SketchUp operations
- **Native API Access**: Full SketchUp Ruby API available
- **Unlimited Flexibility**: Any SketchUp operation possible via Ruby code
- **Educational Value**: Learn valuable SketchUp scripting skills

### Model Introspection (New!)
- **Query Model State**: Get model info without writing Ruby code
- **Entity Inspection**: List faces, edges, groups, components with details
- **Visual Feedback**: Take screenshots to verify modeling results
- **Selection Awareness**: Inspect currently selected entities
- **Layer & Material Discovery**: Browse layers and materials in the model
- **Camera Information**: Get current view position and settings

### Essential Tools
- **Ruby Code Evaluation**: Execute any SketchUp Ruby code for modeling
- **Project-Based Workflow**: Develop Ruby scripts directly in your project
- **Export Capabilities**: SKP, OBJ, STL, PNG, JPG formats
- **Model Introspection**: Query model state, entities, materials, and camera
- **Connection Health**: Reliable communication with SketchUp
- **Console Capture**: Comprehensive logging and output capture system

### Developer Experience
- **Ruby Injection**: Direct source loading via `-RubyStartup` (no file deployment)
- **Live Reloading**: Extension reload without SketchUp restart
- **CLI Reload Scripts**: Command-line tools for instant extension reload during development
- **Modern Toolchain**: UV package management, mise isolation, automated builds
- **Comprehensive Logging**: Color-coded output with detailed progress tracking
- **Git Integration**: Ruby scripts in your project, fully version controllable

## Quick Start

### Prerequisites

- **SketchUp** (2020+) - Any recent version with Ruby API
- **Ruby 3.4.7** - Managed via mise for extension development
- **Python 3.14** - Latest Python with UV package manager
- **Claude Code** - For AI-driven SketchUp automation

### 1. Launch SketchUp with Extension

```bash
# One-command launch with Ruby injection
./scripts/launch-sketchup.sh

# For detailed loading info
SUPEX_VERBOSE=1 ./scripts/launch-sketchup.sh
```

The launcher automatically:
- Validates extension sources
- Injects Ruby extension via `-RubyStartup`
- Starts SketchUp with extension loaded
- Provides graceful shutdown handling

### 2. Start Python MCP Server

```bash
cd src/driver
uv sync --dev
uv run supex-mcp
```

### 3. Connect Claude Code with Supex

Add Supex to your Claude Code configuration:

```json
{
  "mcpServers": {
    "supex": {
      "command": "uv",
      "args": ["run", "supex-mcp"],
      "cwd": "/path/to/supex/src/driver"
    }
  }
}
```

**Detailed Setup Steps:**

1. **Open Claude Code Settings**
   - Use keyboard shortcut **⌘+,** (Cmd+Comma)
   - Or go to **Claude Code > Settings** in the menu bar

2. **Navigate to MCP Servers**
   - Click **MCP Servers** in the left sidebar
   - You'll see the MCP server configuration interface

3. **Add Supex Server**
   - Click the **Add Server** button (+ icon)
   - Fill in the server configuration:
     - **Name**: `supex`
     - **Command**: `uv`
     - **Arguments**: `["run", "supex-mcp"]`
     - **Working Directory**: `/Users/yourname/path/to/supex/src/driver`

4. **Update Paths**
   - Replace `/Users/yourname/path/to/supex` with your actual directory
   - Ensure the path points to the `src/driver` subdirectory
   - Example: `/Users/darwin/x/lab/supex/src/driver`

5. **Save and Restart**
   - Click **Save** to store the configuration
   - **Restart Claude Code** completely to activate the MCP connection
   - The server should appear in the active MCP servers list

### 4. Basic Usage Example

```ruby
# Create a table using SketchUp Ruby API with proper operations
model = Sketchup.active_model
entities = model.active_entities

model.start_operation('Create Simple Table', true)

begin
  # Table dimensions (metric units)
  table_length = 1.2.m
  table_width = 0.8.m
  table_height = 0.75.m
  top_thickness = 0.04.m

  # Create table top
  table_top = entities.add_group
  table_top.name = "Table Top"
  top_face = table_top.entities.add_face(
    [0, 0, table_height - top_thickness],
    [table_length, 0, table_height - top_thickness],
    [table_length, table_width, table_height - top_thickness],
    [0, table_width, table_height - top_thickness]
  )
  top_face.pushpull(top_thickness)

  # Apply wood material
  wood_material = model.materials.add("Wood")
  wood_material.color = Sketchup::Color.new(139, 69, 19)
  table_top.entities.each { |e| e.material = wood_material if e.is_a?(Sketchup::Face) }

  model.commit_operation
  puts "Table created successfully!"

rescue StandardError => e
  model.abort_operation
  puts "Error: #{e.message}"
  raise
end
```

Execute with:
```ruby
# Save script to your project
eval_ruby_file("scripts/create_table.rb")

# Verify with introspection tools
get_model_info()
take_screenshot()

# Export the model
export_scene("skp")
```

## Development Workflow

### Ruby Extension Development

```bash
# 1. Edit Ruby source files in src/runtime/supex_runtime/
# 2. Reload extension (choose one):

# Via command line (recommended for development)
./scripts/reload-extension.sh

# Or using Python script with options
./src/driver/scripts/reload_extension.py --host 127.0.0.1 --port 9876

# Via SketchUp menu
Extensions > Supex Runtime > Reload Extension

# Via MCP tool
reload_extension

# Via Ruby console
SupexRuntime::Main.reload_extension
```

### Ruby Extension Build System

```bash
cd src/runtime

# Install dependencies
bundle install

# Build .rbz package (for production)
bundle exec rake build

# Run code linting
bundle exec rubocop

# Generate documentation
bundle exec yard
```

### Python Server Development

```bash
cd src/driver

# Install with development dependencies
uv sync --dev

# Run tests
uv run pytest tests/ -v

# Code quality
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

## Project Structure

```
supex/
├── scripts/
│   ├── launch-sketchup.sh          # Main SketchUp launcher
│   ├── reload-extension.sh         # CLI reload wrapper (bash)
│   ├── launch-mcp.sh               # MCP server launcher with logging
│   └── helpers/                    # Helper scripts
│       └── shutdown-sketchup.applescript  # Graceful SketchUp shutdown
├── src/
│   ├── driver/                     # Python MCP server
│   │   ├── src/supex_driver/      # Server implementation
│   │   ├── scripts/               # Utility scripts
│   │   │   └── reload_extension.py # CLI reload tool (Python)
│   │   ├── examples/              # Usage examples
│   │   ├── tests/                 # Test suite
│   │   └── pyproject.toml         # UV package config
│   └── runtime/                    # Ruby SketchUp extension
│       ├── injector.rb            # Ruby injection script
│       ├── supex_runtime.rb       # Extension registration
│       ├── supex_runtime/         # Modular Ruby sources
│       ├── Gemfile                # Ruby dependencies
│       └── Rakefile               # Build automation
├── examples/
│   └── simple-table/               # Example project demonstrating workflow
├── CLAUDE.md                       # AI development guidelines
└── README.md                       # This file
```

## Available MCP Tools

### Primary Execution Tools
- **`eval_ruby(code)`** - Execute Ruby code in SketchUp context
- **`eval_ruby_file(file_path)`** - Execute Ruby files with proper error reporting (RECOMMENDED)

### Introspection Tools (New!)
- **`get_model_info()`** - Get model statistics (faces, edges, groups, etc.)
- **`list_entities(entity_type?)`** - List entities in model (faces, edges, groups, components)
- **`get_selection()`** - Get currently selected entities with details
- **`get_layers()`** - List all layers (tags) in the model
- **`get_materials()`** - List all materials with colors and textures
- **`get_camera_info()`** - Get current camera position and settings
- **`take_screenshot(width?, height?, transparent?, output_path?)`** - Capture view and save to disk
  - Returns file path (not image data - saves ~20k tokens!)
  - Use Read tool to view screenshot only if needed
  - Default location: `.tmp/screenshots/screenshot-YYYYMMDD-HHMMSS.png`

### Model Management Tools
- **`open_model(path)`** - Open a SketchUp model file
- **`save_model(path?)`** - Save current model (optionally to new path)
- **`export_scene(format)`** - Export to SKP, OBJ, STL, PNG, JPG

### Connection & Status Tools
- **`check_sketchup_status()`** - Verify connection health
- **`console_capture_status()`** - Check console logging status

**Note**: Extension reload is available via CLI (`./scripts/reload-extension.sh`) or SketchUp menu, not as an MCP tool.

## Advanced Features

### Project-Based Ruby Workflow

Supex follows a project-based workflow where Ruby scripts live directly in your project directories:

```ruby
# Example: scripts/create_spiral_staircase.rb
model = Sketchup.active_model
entities = model.active_entities

# Start operation for undo/redo support
model.start_operation('Create Spiral Staircase', true)

begin
  # Create parametric spiral staircase with proper organization
  steps = 12
  radius = 1.5.m
  height_per_step = 20.cm

  (0...steps).each do |i|
    angle = (2 * Math::PI * i) / steps
    x = radius * Math.cos(angle)
    y = radius * Math.sin(angle)
    z = height_per_step * i

    # Create named step group
    step_group = entities.add_group
    step_group.name = "Step #{i + 1}"

    # Create step geometry
    face = step_group.entities.add_face(
      [x-100.mm, y-50.mm, z], [x+100.mm, y-50.mm, z],
      [x+100.mm, y+50.mm, z], [x-100.mm, y+50.mm, z]
    )
    face.pushpull(20.mm)

    # Apply material
    material = model.materials.add("Wood")
    material.color = [139, 69, 19]
    step_group.material = material
  end

  model.commit_operation
  puts "Spiral staircase created successfully!"

rescue StandardError => e
  model.abort_operation
  puts "Error: #{e.message}"
  raise
end
```

Execute the script with:
```ruby
eval_ruby_file("scripts/create_spiral_staircase.rb")
```

### Project-Based Workflow Benefits

- **Git Integration**: Ruby scripts are version controlled with your project
- **IDE Support**: Full syntax highlighting and code completion in your editor
- **Proper Error Reporting**: Line numbers and stack traces point to actual files
- **Code Reusability**: Scripts can be shared and reused across projects
- **Team Collaboration**: Multiple developers can work on the same modeling scripts
- **Example Projects**: See `examples/simple-table/` for complete workflow demonstration

### Extension Development Cycle

1. **Edit** Ruby extension sources in `src/runtime/supex_runtime/`
2. **Reload** extension via CLI: `./scripts/reload-extension.sh`
3. **Test** changes immediately without SketchUp restart
4. **Iterate** rapidly with instant feedback

For project scripts, simply edit and re-run with `eval_ruby_file()`.

## Technical Architecture

### Ruby Injection System
- **Direct Loading**: Sources loaded via `$LOAD_PATH` manipulation
- **No File Copying**: Extension sources remain in development directory
- **Injector Script**: `injector.rb` handles Ruby environment setup
- **SketchUp Integration**: Uses `-RubyStartup` flag for seamless injection

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

## 🔗 Claude Code Integration

### Project-Based Development Workflow

Supex enables AI-driven SketchUp automation through configured Claude Code projects. See `examples/simple-table/` for a complete working template.

**Setup Steps:**

1. **Launch SketchUp** with Supex extension:
   ```bash
   ./scripts/launch-sketchup.sh  # From supex repo root
   ```

2. **Configure your Claude Code project** with `.claude/mcp.json`:
   ```json
   {
     "mcpServers": {
       "supex": {
         "command": "uv",
         "args": ["run", "supex-mcp"],
         "cwd": "/path/to/supex/src/driver"
       }
     }
   }
   ```

3. **Create project structure**:
   ```
   your-project/
   ├── .claude/
   │   └── mcp.json          # MCP server configuration
   ├── CLAUDE.md             # Project-specific guidance for Claude
   ├── scripts/              # Ruby modeling scripts (version controlled)
   │   ├── create_model.rb
   │   └── add_details.rb
   └── _tmp/                 # Git-ignored temporary files
       └── screenshots/      # Screenshot outputs
   ```

4. **Start creating**: Open project in Claude Code and describe what you want to build

### Development Cycle

The workflow follows a project-based approach where Ruby scripts live in your repository:

```
You: "Create a dining table with 4 legs"

Claude Code workflow:
1. Creates scripts/create_table.rb with proper SketchUp API patterns
2. Executes using eval_ruby_file (proper error reporting with line numbers)
3. Verifies results using introspection tools:
   - get_model_info() - Entity counts and model state
   - take_screenshot() - Visual preview (saves to _tmp/screenshots/)
   - list_entities() - Inspect created geometry
4. Iterates based on your feedback - edit Ruby files and re-run

All Ruby scripts remain in your project for:
- Version control (git)
- IDE editing with syntax highlighting
- Reuse and modification
- Learning SketchUp API patterns
```

**Key Tools:**
- `eval_ruby_file` - Execute Ruby scripts with proper error context
- `get_model_info()` - Check entity counts and model state
- `take_screenshot()` - Save visual preview (returns path only, ~200 tokens vs 21k)
- `list_entities()` - Inspect geometry hierarchy
- `get_selection()` - Verify selections

### Example Project Template

See `examples/simple-table/` for a complete working example showing:
- Project configuration (`.claude/mcp.json`, `CLAUDE.md`)
- Ruby script organization (`scripts/create_table.rb`, `scripts/add_decorations.rb`)
- Modular development approach (separate scripts for different features)
- Best practices from SketchUp API (operations, groups, materials)

Copy and adapt this template as a starting point for your own projects.

### AI-Driven Ruby Scripting

- **Project-Based**: Ruby scripts in version-controlled directory structure
- **Natural Language**: Describe what you want to build
- **Ruby Expertise**: Built-in knowledge of SketchUp Ruby API patterns
- **Educational Approach**: Learn SketchUp scripting through generated examples
- **Modular Organization**: Separate scripts for different features and utilities
- **Iterative Development**: Edit Ruby files in your IDE and re-run
- **Live Feedback**: Introspection tools verify results in real-time

## Contributing

### Development Setup

1. **Clone repository**
2. **Setup Ruby environment**: `mise install`
3. **Setup Python environment**: `cd src/driver && uv sync --dev`
4. **Launch development**: `./scripts/launch-sketchup.sh`
5. **Configure Claude Code**: Add MCP server configuration

### Code Quality

- **Ruby**: RuboCop linting, YARD documentation, Test::Unit testing
- **Python**: Ruff formatting/linting, mypy type checking, pytest testing
- **Git**: Conventional commits with detailed change descriptions

## Requirements

### System Requirements
- **macOS** (primary target) - Full AppleScript integration
- **SketchUp 2020+** - Modern Ruby API support
- **Ruby 3.4.7** - Latest features and performance improvements
- **Python 3.14** - Latest performance and type system enhancements

### Development Tools
- **mise** - Multi-language version management
- **bundler** - Ruby dependency management
- **UV** - Python package management
- **git** - Version control

## License

MIT License - see LICENSE file for details.

---

**Supex** provides a Ruby scripting platform for SketchUp that enables AI agents to execute native SketchUp code via MCP. Focus on direct API access provides unlimited modeling flexibility, educational value, and transferable SketchUp scripting skills.