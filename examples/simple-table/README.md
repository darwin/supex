# Simple Table Example - Complete Tutorial

This example provides a complete step-by-step introduction to Supex, showing you how to create 3D models in SketchUp using Ruby scripts and Claude Code.

## What You'll Learn

By the end of this tutorial, you'll know how to:
- Set up Supex with SketchUp and Claude Code
- Write and execute Ruby scripts to create 3D geometry
- Use introspection tools to verify your models
- Save and iterate on your designs
- Start your own SketchUp automation projects

## Prerequisites

Before starting, make sure you have:

### 1. SketchUp 2026

Download from [sketchup.com](https://www.sketchup.com) if you haven't already.

**Verify installation:**
- Can you launch SketchUp?
- Is it version 2026? (Check SketchUp → About SketchUp)
- Note: Only latest SketchUp is tested (project is experimental)

### 2. Claude Code

Download from [claude.ai/code](https://claude.ai/code) if you haven't already.

**Verify installation:**
- Can you launch Claude Code from your terminal?
- Try running `claude --version`

**Note:** This tutorial uses Claude Code, but other MCP-compatible AI agents might work (untested).

### 3. Supex Installation

You should have cloned or downloaded the Supex repository.

**Verify you have Supex:**
```bash
# Check if you have the Supex directory
ls /path/to/supex/mcp  # Should show the mcp wrapper script
```

## Step 1: Install Supex Extension in SketchUp

### For Testing/Development

If you're using Supex from the repository:

```bash
# From the Supex repository root
cd /path/to/supex
./scripts/launch-sketchup.sh
```

This will:
- Validate the extension sources
- Launch SketchUp with the Supex extension loaded
- The extension will start a socket server (port 9876)

**Verify the extension loaded:**
1. SketchUp should launch
2. Look for "Supex Runtime" in the Ruby Console
3. You should see "Socket server started on port 9876"

If you see any errors, check the [Troubleshooting](#troubleshooting) section below.

## Step 2: Configure Claude Code

You need to tell Claude Code where to find the Supex MCP server.

### Create .mcp.json

In the `examples/simple-table/` directory (this directory), create a file named `.mcp.json`:

```json
{
  "mcpServers": {
    "supex": {
      "command": "/absolute/path/to/supex/mcp"
    }
  }
}
```

**Important**: Replace `/absolute/path/to/supex/mcp` with the actual absolute path to the `mcp` file in your Supex installation.

Example:
```json
{
  "mcpServers": {
    "supex": {
      "command": "/Users/yourusername/projects/supex/mcp"
    }
  }
}
```

**Note**: The path must be absolute (not relative). Use `pwd` in the supex directory to get the full path:

```bash
cd /path/to/supex
pwd  # Copy this path and append /mcp
```

### Verify Configuration

**Claude Code automatically starts the MCP server** - you don't need to run anything manually.

To verify it's working:
1. Open Claude Code in the `examples/simple-table/` directory
2. The MCP server should automatically connect
3. You should have access to Supex tools like `check_sketchup_status`

## Step 3: Create Your First Model

Now you're ready to create your first 3D model! Let's build a simple table.

### Understanding the Project Structure

```
simple-table/
├── .mcp.json               # Supex configuration (you just created this)
├── CLAUDE.md               # AI guidance for this project
├── README.md               # This file
└── scripts/
    ├── create_table.rb     # Main script - creates the table
    └── add_decorations.rb  # Additional script - adds trim
```

### Execute the Table Script

In Claude Code, ask:

```
Run the create_table.rb script to create a simple table in SketchUp
```

Or use the tool directly:
```
eval_ruby_file("scripts/create_table.rb")
```

**What happens:**
1. Claude Code sends the command to the MCP server
2. MCP server forwards it to SketchUp
3. SketchUp executes the Ruby code
4. A table with 4 legs appears in your model!

### Verify the Results

Check what was created using introspection tools:

```
get_model_info()
```

This returns entity counts:
```json
{
  "faces": 30,
  "edges": 120,
  "groups": 5,
  "component_instances": 0
}
```

Take a screenshot to see the visual result:

```
take_screenshot()
```

This saves a screenshot to `_tmp/screenshots/` and returns the file path.

**Note**: The tool returns just the file path (saves tokens). Only use `Read` on the screenshot if you need to see it.

### Inspect the Geometry

See what groups were created:

```
list_entities('groups')
```

This shows:
```json
[
  {"name": "Table Top", "visible": true, "layer": "Layer0"},
  {"name": "Leg 1", "visible": true, "layer": "Layer0"},
  {"name": "Leg 2", "visible": true, "layer": "Layer0"},
  {"name": "Leg 3", "visible": true, "layer": "Layer0"},
  {"name": "Leg 4", "visible": true, "layer": "Layer0"}
]
```

## Step 4: Add Details

Now let's add decorative trim to the table.

### Execute the Decorations Script

```
eval_ruby_file("scripts/add_decorations.rb")
```

### Verify the Changes

Check the updated entity counts:
```
get_model_info()
```

You should see more faces and edges now!

## Step 5: Save Your Model

Save the model to this project directory:

```
save_model("model.skp")
```

Now you have a SketchUp file you can open and modify anytime!

## Understanding the Code

Let's look at what the `create_table.rb` script does.

### Basic Structure

Every SketchUp Ruby script follows this pattern:

```ruby
# Get the active model
model = Sketchup.active_model
entities = model.active_entities

# Start an operation (enables undo/redo)
model.start_operation('Operation Name', true)

begin
  # Your modeling code here

  model.commit_operation  # Commit the changes
rescue StandardError => e
  model.abort_operation   # Rollback on error
  raise
end
```

### Creating the Table Top

```ruby
# Create a group for the table top
table_top = entities.add_group
table_top.name = "Table Top"

# Create a rectangle face
face = table_top.entities.add_face(
  [-60.cm, -40.cm, 0],  # Bottom-left corner
  [60.cm, -40.cm, 0],   # Bottom-right corner
  [60.cm, 40.cm, 0],    # Top-right corner
  [-60.cm, 40.cm, 0]    # Top-left corner
)

# Extrude it to create thickness
face.pushpull(-5.cm)
```

### Key Concepts

**Metric Units:**
- Use `.cm`, `.m`, `.mm` for readable dimensions
- Example: `120.cm` = 120 centimeters

**Groups:**
- Organize geometry into named groups
- Makes the model structure clear
- Easier to select and modify

**Operations:**
- `start_operation` / `commit_operation` enable undo/redo
- Always wrap modeling code in operations
- Use `abort_operation` if something fails

**Materials:**
```ruby
material = model.materials.add("Wood")
material.color = [139, 69, 19]  # RGB values
table_top.material = material
```

## Modifying the Example

Try making changes to learn more!

### Change Dimensions

Edit `create_table.rb`:

```ruby
# Make the table bigger
table_width = 180.cm   # instead of 120.cm
table_depth = 90.cm    # instead of 80.cm
table_height = 75.cm   # instead of 73.cm
```

Then re-run the script:
```
eval_ruby_file("scripts/create_table.rb")
```

### Change Colors

Try different materials:

```ruby
# Make it a different wood color
material.color = [101, 67, 33]  # Darker brown

# Or use a named color
material.color = "BurlyWood"
```

### Add More Geometry

Create a drawer:

```ruby
drawer = entities.add_group
drawer.name = "Drawer"

# Create drawer geometry
drawer_face = drawer.entities.add_face(...)
drawer_face.pushpull(...)
```

## Troubleshooting

### Extension Not Loading

**Symptom**: SketchUp launches but no "Supex Runtime" message in Ruby Console

**Solutions:**
1. Check the Ruby Console for errors (Window → Ruby Console)
2. Verify you're using `./scripts/launch-sketchup.sh` from the supex repo root
3. Check file permissions on `src/runtime/` directory
4. Try: `SUPEX_VERBOSE=1 ./scripts/launch-sketchup.sh` for detailed output

### MCP Connection Failed

**Symptom**: Claude Code can't find Supex tools

**Solutions:**
1. Verify `.mcp.json` exists in the project root
2. Check the path in `.mcp.json` is absolute (not relative)
3. Make sure SketchUp is running with the extension
4. Check `.tmp/supex-mcp.log` for error messages

### Script Execution Fails

**Symptom**: `eval_ruby_file` returns an error

**Solutions:**
1. Check Ruby Console in SketchUp for detailed error
2. Verify the script file path is correct
3. Look for syntax errors in the Ruby code
4. Make sure SketchUp model is active (not in startup screen)

### Socket Connection Refused

**Symptom**: "Connection refused" error when executing commands

**Solutions:**
1. Verify SketchUp is running
2. Check the extension is loaded (Ruby Console should show "Socket server started")
3. Verify port 9876 isn't used by another application:
   ```bash
   lsof -i :9876
   ```
4. Try restarting SketchUp

### Can't Find Files

**Symptom**: "File not found" when using `eval_ruby_file`

**Solutions:**
1. Use paths relative to project root: `scripts/create_table.rb`
2. Or use absolute paths: `/full/path/to/script.rb`
3. Verify file exists: `ls scripts/create_table.rb`

## Next Steps

Now that you've completed this tutorial, you can:

### 1. Create Your Own Project

```bash
mkdir my-sketchup-project
cd my-sketchup-project

# Create project structure
mkdir scripts
mkdir _tmp

# Copy the .mcp.json template
cp /path/to/supex/examples/simple-table/.mcp.json .

# Create your first script
touch scripts/my_model.rb
```

### 2. Learn More About SketchUp Ruby API

- [SketchUp Ruby API Documentation](https://ruby.sketchup.com)
- [SketchUp Developer Center](https://developer.sketchup.com)
- Try the examples in `src/driver/resources/`

### 3. Explore Supex Tools

See the main [README.md](../../README.md) for:
- Complete MCP tools reference
- Advanced features
- Architecture overview
- More examples

### 4. Read the Workflow Guide

Check `src/driver/prompts/sketchup_workflow.md` for:
- Best practices
- Common patterns
- Tips and tricks
- Performance optimization

### 5. Get Help

- **Issues**: Report bugs on GitHub
- **Discussions**: Ask questions and share your projects
- **Documentation**: Check the main README and CONTRIBUTE.md

## Key Takeaways

- **Project-based workflow**: Ruby scripts live in your project directory
- **Git-trackable**: All your modeling code is version controlled
- **Iterative**: Edit scripts and re-run to see changes
- **Introspection**: Use tools like `get_model_info()` and `take_screenshot()` to verify
- **Learning platform**: Generated code teaches you SketchUp Ruby API patterns

Happy modeling with Supex!
