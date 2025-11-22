# Supex Driver: SketchUp Model Context Protocol Server

Supex is a modern SketchUp integration that enables AI agents to control and manipulate 3D scenes through the Model Context Protocol (MCP). This is a complete reimplementation that incorporates the latest MCP patterns while preserving all SketchUp-specific functionality.

## Features

### Core Geometry
- **Basic Shapes**: Create cubes, cylinders, spheres, and cones
- **Transformations**: Position, rotate, and scale components
- **Materials**: Apply colors and materials to objects
- **Selection**: Get and manipulate selected entities

### Advanced Features
- **Export Options**: Multiple format support (SKP, OBJ, STL, images)
- **Ruby Code Evaluation**: Execute arbitrary Ruby code in SketchUp context
- **Status Checking**: Monitor connection health
- **Strategic AI Guidance**: Built-in 3D modeling expertise prompts
- **Component Naming**: Organized models with descriptive names
- **Robust Error Handling**: Comprehensive logging and recovery

## Requirements

- **Python 3.14+** - Latest Python with enhanced performance and new language features
- **UV** - Modern Python package manager ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
- **SketchUp** - Any recent version with Ruby API support

### Python 3.14 Benefits
- **Enhanced Performance**: Improved bytecode interpreter and memory management
- **Better Error Messages**: More precise and helpful error diagnostics  
- **Type System Improvements**: Enhanced type annotations and better mypy support
- **Security Enhancements**: Latest security patches and hardening features

## Installation

### 1. Install Python Package

```bash
cd src/driver

# Install with UV (recommended)
uv sync

# Alternative: Install with pip
pip install -e .
```

### 2. Install SketchUp Extension

**Recommended: Use the launcher script from the repository root:**

```bash
# From the main supex directory
./launch-sketchup.sh
```

This automatically handles extension loading via Ruby injection.

**Alternative: Manual installation:**

1. Build and install the extension:
   ```bash
   cd src/runtime
   bundle install
   bundle exec rake build
   bundle exec rake install
   ```

2. Restart SketchUp

3. Go to **Extensions > Extension Manager** and enable "Supex Runtime"

## Usage

### 1. Start the SketchUp Extension

**With Launcher Script (Recommended):**
```bash
# From repository root - automatically starts extension
./launch-sketchup.sh
```

**Manual Method:**
In SketchUp:
- Go to **Extensions > Supex Runtime > Start Server**
- The extension will start listening on localhost:9876

### 2. Run the MCP Server

```bash
# UV method (recommended)
uv run supex-mcp

# Alternative methods
supex-mcp                  # If installed globally
python -m supex_driver    # Module execution
```

### 3. Connect with MCP Client

The server provides these tools:

#### Geometry Creation
- `create_component(type, position, dimensions)` - Create basic shapes
- `delete_component(id)` - Remove components
- `transform_component(id, position, rotation, scale)` - Transform objects

#### Materials & Selection
- `set_material(id, material)` - Apply colors/materials
- `get_selection()` - Get selected entities
- `check_sketchup_status()` - Verify connection

#### Export & Evaluation
- `export_scene(format)` - Export to various formats
- `eval_ruby(code)` - Execute Ruby code in SketchUp

#### AI Guidance
- `modeling_strategy()` - Get strategic 3D modeling advice

## Examples

### Basic Shapes
```python
# Create a table top with descriptive name
table_top = create_component("cube", [0, 0, 0], [6, 4, 0.5], "Table Top")
set_material(table_top["id"], "#8B4513")

# Create cylindrical table legs
for i, pos in enumerate([[0, 0, -2], [5.5, 0, -2], [0, 3.5, -2], [5.5, 3.5, -2]]):
    leg = create_component("cylinder", pos, [0.3, 0.3, 2], f"Table Leg {i+1}")
    set_material(leg["id"], "#8B4513")
```

### Complex Model
```python
# Create a modern chair design
seat = create_component("cube", [0, 0, 1.5], [2, 2, 0.2], "Chair Seat")
backrest = create_component("cube", [0, 1.8, 1.7], [2, 0.2, 1.5], "Chair Back")
set_material(seat["id"], "#4A4A4A")
set_material(backrest["id"], "#4A4A4A")

# Add decorative sphere
accent = create_component("sphere", [1, 1, 3.5], [0.3, 0.3, 0.3], "Accent Sphere")
set_material(accent["id"], "#FF6B35")
```

### Advanced Ruby Scripting
```python
# Create complex geometry with Ruby
code = '''
# Create a parametric spiral staircase
model = Sketchup.active_model
entities = model.active_entities

steps = 12
radius = 5.feet
height_per_step = 8.inches

(0...steps).each do |i|
  angle = (2 * Math::PI * i) / steps
  x = radius * Math.cos(angle)
  y = radius * Math.sin(angle)
  z = height_per_step * i
  
  # Create step
  group = entities.add_group
  face = group.entities.add_face(
    [x-1, y-0.5, z],
    [x+1, y-0.5, z], 
    [x+1, y+0.5, z],
    [x-1, y+0.5, z]
  )
  face.pushpull(2.inches)
end
'''

eval_ruby(code)
```

## Architecture

Supex uses a dual-process architecture:

1. **Python MCP Server** (`src/supex_driver/mcp/server.py`)
   - Handles MCP protocol communication
   - Provides tool interfaces for AI agents
   - Manages connection lifecycle
   - Implements robust error handling

2. **Ruby SketchUp Extension** (`src/runtime/`)
   - Runs inside SketchUp process with Ruby injection
   - Modular architecture with focused components
   - Executes actual geometry operations
   - Provides socket server for communication
   - Integrates with SketchUp Ruby API
   - Supports live reloading during development

Communication happens over TCP sockets using JSON-RPC 2.0 protocol.

## Development

### Project Structure
```
supex/
├── scripts/
│   └── launch-sketchup.sh     # Main launcher script
├── src/
│   ├── driver/               # Python MCP server
│   │   ├── src/supex_driver/ # Server implementation
│   │   ├── examples/         # Usage examples
│   │   ├── tests/            # Test suite
│   │   └── pyproject.toml    # Python package config
│   └── runtime/              # Ruby SketchUp extension
│       ├── supex_runtime/    # Modular Ruby sources
│       ├── injector.rb       # Ruby injection script
│       ├── Gemfile           # Ruby dependencies
│       └── Rakefile          # Build automation
├── CLAUDE.md                 # AI development guidelines
└── README.md                 # Main documentation
```

### Key Implementation Details

- **Modern MCP Patterns**: Uses latest FastMCP framework with async lifecycle management
- **Robust Connection Handling**: Automatic reconnection and health checking  
- **Comprehensive Error Handling**: Multi-layer error handling with user-friendly messages
- **SketchUp Integration**: Full Ruby API access with geometry operations
- **3D Modeling Focus**: Comprehensive tools for general 3D modeling and design

## Development

### Setup Development Environment

```bash
# From repository root
cd src/driver
uv sync --dev

# Ruby extension setup
cd ../runtime
bundle install
```

### Development Commands

```bash
# Run linting
uv run ruff check src/ tests/

# Format code  
uv run ruff format src/ tests/

# Type checking
uv run mypy src/

# Run tests
uv run pytest tests/ -v

# Run server in development mode
uv run python -m supex_driver
```

### Testing Connection

```bash
# Test SketchUp connection
uv run python -c "
from supex_driver.adapter.connection import get_sketchup_connection
conn = get_sketchup_connection()
result = conn.send_command('ping')
print('Connected:', result)
"
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

For issues and feature requests, please use the GitHub issue tracker.