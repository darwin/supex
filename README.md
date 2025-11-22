# Supex: SketchUp Automation via Model Context Protocol

An experimental SketchUp automation platform that enables AI agents to execute native SketchUp Ruby code through the Model Context Protocol (MCP). Designed as a complement to traditional UI-based modeling, currently suitable for programmers with agentic coding experience who want to augment their SketchUp workflow with direct API access and flexible Ruby scripting.

## Architecture Overview

Supex bridges AI agents with SketchUp through a client-server architecture:

1. **Ruby SketchUp Extension** (`src/runtime/`)
   - Runs inside SketchUp process
   - Executes Ruby code in SketchUp's API context
   - Provides socket server for external communication

2. **Python MCP Driver** (`src/driver/`)
   - MCP server for AI agent integration (FastMCP framework)
   - CLI for status monitoring and diagnostics
   - Connects to SketchUp via TCP socket adapter

The driver and extension communicate via TCP sockets (localhost:9876) using JSON-RPC 2.0, enabling AI agents to execute Ruby code directly in SketchUp's context and inspect model state in real-time.

## Key Features

### Direct Ruby API Access
- **Full SketchUp Ruby API**: Execute any SketchUp operation via Ruby code
- **eval_ruby & eval_ruby_file**: Run code inline or from project scripts
- **Unlimited Flexibility**: No constraints on what you can create or modify
- **Educational Value**: Learn SketchUp scripting through AI-generated examples

### Model Introspection
- **Entity Inspection**: List and examine faces, edges, groups, components with details
- **Visual Verification**: Take screenshots to verify modeling results
- **Selection & Context**: Inspect currently selected entities
- **Materials & Layers**: Browse materials and layers in the model
- **Camera Information**: Query current view position and settings
- **Model Statistics**: Get comprehensive model state without writing code

### Project-Based Development
- **Scripts in Your Repository**: Ruby files live in your project directory structure
- **Version Control Ready**: Full git integration for modeling scripts
- **IDE Support**: Edit scripts with syntax highlighting and RuboCop
- **Modular Organization**: Separate scripts for different features and utilities
- **Export Capabilities**: SKP, OBJ, STL, PNG, JPG formats

### Developer Experience
- **Live Reloading**: Reload extension without restarting SketchUp
- **CLI Tools**: Status monitoring, diagnostics, and reload scripts
- **Ruby Injection**: Direct source loading via `-RubyStartup` flag
- **Comprehensive Logging**: Color-coded output with detailed progress tracking
- **Console Capture**: Real-time Ruby console output and error reporting

## Quick Start

The fastest way to get started with Supex is through our complete example project.

### Prerequisites

- **SketchUp 2020+** - Download from [sketchup.com](https://www.sketchup.com)
- **Claude Code** - AI-powered development environment from [claude.ai/code](https://claude.ai/code)

### Try the Example Project

See the **[Simple Table Example](examples/simple-table/README.md)** for a complete step-by-step tutorial that covers:

1. **Installation** - Setting up Supex extension in SketchUp
2. **Configuration** - Connecting Claude Code with Supex
3. **First Model** - Creating a table with Ruby scripts
4. **Verification** - Using introspection tools to verify results
5. **Next Steps** - Building your own projects

The example project includes working Ruby scripts, detailed explanations, and troubleshooting help.

### Quick Configuration Reference

For experienced users, add Supex to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "supex": {
      "command": "/absolute/path/to/supex/mcp"
    }
  }
}
```

Claude Code automatically starts the MCP server when configured.

### For Developers

If you want to contribute to Supex development, see [CONTRIBUTE.md](CONTRIBUTE.md) for development environment setup.

## Project Organization

Supex is organized to separate the core system from your modeling projects:

```
supex/                          # Supex installation (this repository)
├── mcp                         # MCP server (referenced in your .mcp.json)
├── examples/
│   └── simple-table/           # Example project - start here!
└── [src/, scripts/, ...]       # Core implementation (see CONTRIBUTE.md)

your-project/                   # Your SketchUp project
├── .mcp.json                   # Supex configuration
├── CLAUDE.md                   # Project-specific AI guidance
├── scripts/                    # Your Ruby modeling scripts
│   ├── create_model.rb
│   └── add_details.rb
└── _tmp/                       # Screenshots and temporary files
    └── screenshots/
```

For detailed implementation structure, see [CONTRIBUTE.md](CONTRIBUTE.md).

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

**Note**: Extension reload is available via CLI (`supex reload`) or SketchUp menu, not as an MCP tool.

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

**Workflow**: Create or edit Ruby scripts in your project's `scripts/` directory, then execute them with `eval_ruby_file()`. Iterate by modifying the scripts and re-running.

## Claude Code Integration

### Project-Based Development Workflow

Supex enables AI-driven SketchUp automation through configured Claude Code projects. See `examples/simple-table/` for a complete working template.

**Setup Steps:**

1. **Launch SketchUp** with Supex extension:
   ```bash
   ./scripts/launch-sketchup.sh  # From supex repo root
   ```

2. **Configure your Claude Code project** with `.mcp.json` in project root:
   ```json
   {
     "mcpServers": {
       "supex": {
         "command": "/path/to/supex/mcp"
       }
     }
   }
   ```

3. **Create project structure**:
   ```
   your-project/
   ├── .mcp.json             # MCP server configuration
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
- Project configuration (`.mcp.json`, `CLAUDE.md`)
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

We welcome contributions to Supex! If you'd like to help improve Supex:

- **Report Issues**: Found a bug? Open an issue on GitHub
- **Suggest Features**: Have an idea? Start a discussion
- **Submit Pull Requests**: Want to contribute code? See [CONTRIBUTE.md](CONTRIBUTE.md) for:
  - Development environment setup
  - Code quality standards
  - Testing guidelines
  - Contribution process

See [CONTRIBUTE.md](CONTRIBUTE.md) for complete development documentation.

## Requirements

To use Supex, you need:

- **SketchUp 2020+** - Download from [sketchup.com](https://www.sketchup.com)
- **Claude Code** - AI-powered development environment from [claude.ai/code](https://claude.ai/code)
- **macOS** - Currently the primary supported platform

For development requirements, see [CONTRIBUTE.md](CONTRIBUTE.md).

## License

MIT License - see LICENSE file for details.

---

**Supex** provides a Ruby scripting platform for SketchUp that enables AI agents to execute native SketchUp code via MCP. Focus on direct API access provides unlimited modeling flexibility, educational value, and transferable SketchUp scripting skills.