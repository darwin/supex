# Supex: SketchUp Automation for AI Agents

An experimental SketchUp automation platform that enables AI agents to execute native SketchUp Ruby code through the Model Context Protocol (MCP). Designed as a complement to traditional UI-based modeling, currently suitable for programmers with agentic coding experience who want to augment their SketchUp workflow with direct API access and flexible Ruby scripting.

## Architecture Overview

Supex bridges AI agents and CLI tools with SketchUp through a client-server architecture:

```
┌─────────────────┐                              ┌─────────────────┐
│   Claude Code   │                              │   CLI Tools     │
│   (AI Agent)    │                              │   ./supex       │
└────────┬────────┘                              └────────┬────────┘
         │                                                │
         │ MCP Protocol                                   │ Direct
         │ (stdio)                                        │ Commands
         │                                                │
         └────────────────┬───────────────────────────────┘
                          ▼
                 ┌─────────────────┐
                 │  Python Driver  │
                 │  (src/driver/)  │
                 │                 │
                 │  • MCP Server   │ ◄── Interface for AI agents
                 │  • CLI Handler  │ ◄── Interface for commands
                 │  • Socket Client│
                 └────────┬────────┘
                          │
                          │ TCP Socket (localhost:9876)
                          │ JSON-RPC 2.0
                          ▼
                 ┌─────────────────┐
                 │ SketchUp Runtime│
                 │ (src/runtime/)  │
                 │                 │
                 │ • Ruby Extension│
                 │ • Socket Server │
                 │ • SketchUp API  │
                 └─────────────────┘
                          │
                          ▼
                  [ SketchUp Process ]
```

**Key Components:**

1. **Python Driver** (`src/driver/`) - Central hub with two interfaces:
   - **MCP Server**: For AI agent integration (FastMCP framework)
   - **CLI Handler**: For direct command-line interaction
   - **Socket Client**: Communicates with SketchUp extension

2. **SketchUp Runtime** (`src/runtime/`) - Ruby extension:
   - Runs inside SketchUp process
   - Executes Ruby code in SketchUp's API context
   - Provides socket server for external communication

**Communication**: TCP sockets (localhost:9876) with JSON-RPC 2.0 protocol enable AI agents and CLI tools to execute Ruby code directly in SketchUp's context and inspect model state in real-time.

## Key Features

### Direct Ruby API Access
- **Full SketchUp Ruby API**: Execute any SketchUp operation via Ruby code
- **eval_ruby & eval_ruby_file**: Run code inline or from project scripts
- **Unlimited Flexibility**: No constraints on what you can create or modify

### Model Introspection
- **Entity Inspection**: List and examine faces, edges, groups, components with details
- **Visual Verification**: Take screenshots to verify modeling results
- **Selection & Context**: Inspect currently selected entities
- **Materials & Layers**: Browse materials and layers in the model
- **Camera Information**: Query current view position and settings
- **Model Statistics**: Get comprehensive model state without writing code

### Project-Based Workflow
- **Scripts in Your Repository**: Ruby files live in your project directory structure
- **Version Control Ready**: Full git integration for modeling scripts
- **IDE Support**: Edit scripts with syntax highlighting and RuboCop
- **Modular Organization**: Separate scripts for different features and utilities
- **Export Capabilities**: SKP, OBJ, STL, PNG, JPG formats

## Quick Start

The fastest way to get started with Supex is through our complete example project.

See the **[Simple Table Example](examples/simple-table/README.md)** for a complete step-by-step tutorial that covers:

1. **Installation** - Setting up Supex extension in SketchUp
2. **Configuration** - Connecting Claude Code with Supex
3. **First Model** - Creating a table with Ruby scripts
4. **Verification** - Using introspection tools to verify results
5. **Next Steps** - Building your own projects

The example project includes working Ruby scripts, detailed explanations, and troubleshooting help.

## Supex CLI

The `supex` command-line interface provides tools for interacting with SketchUp:

### Key Commands

```bash
# Execute Ruby script in SketchUp
./supex eval-file scripts/my_model.rb

# Check connection status
./supex status

# Get model information
./supex info

# Reload the extension (during development)
./supex reload
```

### All Available Commands

For a complete list of commands and options:

```bash
./supex --help
```

The CLI provides access to all SketchUp operations including:
- Script execution
- Model introspection (entities, materials, layers, camera)
- Screenshots and visual verification
- Model management (open, save, export)
- Connection diagnostics

## Project-Based Workflow Explained

Supex recommends a **project-based workflow** where Ruby scripts live directly in your project directory, alongside your other project files. This approach treats 3D modeling code the same way you treat application code.

### The Concept

Instead of writing Ruby code in SketchUp's Ruby Console or as one-off scripts, you organize modeling logic into version-controlled files:

```
your-project/
└── scripts/
    ├── create_table.rb    # Create base geometry
    ├── add_details.rb     # Add decorative elements
    └── materials.rb       # Apply materials
```

Create and run your modeling scripts:

```bash
# First, launch SketchUp with Supex extension
./scripts/launch-sketchup.sh

# Then execute your script in SketchUp
./supex eval-file scripts/create_table.rb

# ... iterate on your code
```

### Key Benefits

- **Version Control**: All modeling code tracked in git alongside your project
- **IDE Integration**: Full syntax highlighting, autocomplete, and linting in your editor
- **Team Collaboration**: Multiple people can work on the same modeling scripts
- **Code Reusability**: Share and reuse scripts across projects
- **Proper Error Reporting**: Line numbers and stack traces point to actual files
- **Modular Organization**: Separate concerns into focused scripts

### Perfect for Agentic Coding

This workflow is ideal for **AI-driven development** with tools like Claude Code:

**How it works:**
1. **AI writes SketchUp Ruby code**
2. **Code is being developed as project files** in your `scripts/` directory
3. **AI executes the code** in SketchUp (typically uses `eval_ruby_file()` tool in Supex MCP)
4. **AI verifies results** using introspection tools in Supex MCP:
   - `get_model_info()` - Entity counts and model state
   - `take_screenshot()` - Visual verification
   - `list_entities()` - Inspect geometry hierarchy

**Feedback loop:**
The introspection tools give AI agents immediate feedback about the model state, enabling iterative refinement without human intervention. The AI can:
- Create geometry
- Verify it was created correctly
- Adjust and re-run if needed
- Learn SketchUp API patterns through iteration

**See it in action:**
Check out [examples/simple-table/](examples/simple-table/README.md) for a complete tutorial showing this workflow in practice.

### AI-Driven Ruby Scripting

- **Project-Based**: Ruby scripts in version-controlled directory structure
- **Natural Language**: Describe what you want to build
- **Ruby Expertise**: Built-in knowledge of SketchUp Ruby API patterns
- **Educational Approach**: Learn SketchUp scripting through generated examples
- **Modular Organization**: Separate scripts for different features and utilities
- **Iterative Development**: Edit Ruby files in your IDE and re-run
- **Live Feedback**: Introspection tools verify results in real-time

## Contributing

If you'd like to help improve Supex:

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