# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an example project demonstrating the project-based workflow for Supex (SketchUp Model Context Protocol). It shows how to create 3D models in SketchUp using Ruby scripts stored in your project directory.

## Prerequisites

This example requires:
- SketchUp running with Supex extension loaded
- Supex server configured in Claude Code
- Parent repository setup at `/path/to/supex`

To launch SketchUp with the extension:
```bash
cd /path/to/supex
./scripts/launch-sketchup.sh
```

## Working with Scripts

### Executing Scripts

Run Ruby scripts in SketchUp using the `eval_ruby_file` tool:
- `scripts/create_table.rb` - Creates a basic wooden table with four legs
- `scripts/add_decorations.rb` - Adds decorative trim (requires table to exist)

### Verifying Results

After running scripts, use introspection tools:
- `get_model_info()` - Check entity counts and model state
- `take_screenshot()` - Get visual preview of the model
  - Automatically saved to `.tmp/screenshots/` directory
  - Tool returns file path only (saves ~21k tokens vs returning image data)
  - Only use Read tool on screenshot if user explicitly asks to see it
- `list_entities('groups')` - Inspect created groups and components
- `get_selection()` - Verify what's selected

### Saving Work

Use `save_model("model.skp")` to save the model to the project directory.

## Script Architecture

**Procedural Programming Approach:**
- **Use procedural style by default** - Structure code into well-defined functions unless user specifies otherwise
- Break down modeling tasks into reusable functions (e.g., `create_table_leg()`, `create_table_top()`)
- Each function should have a single, clear responsibility
- Document functions with YARD comments describing parameters and return values
- Main execution section should orchestrate high-level operations by calling functions

Scripts follow SketchUp best practices:
- Always use `model.start_operation()` / `model.commit_operation()` for undo/redo support
- Organize geometry in named groups for better structure
- Use metric units (e.g., `1.2.m`)
- Wrap operations in begin/rescue blocks with `model.abort_operation` on error
- Add materials for visual appearance

## Best Practices for Reusable Scripts

**Module Organization:**
- **Wrap all functions in a module with Supex prefix** - Use `module SupexXxxYyy` to prevent naming conflicts with other extensions
- **No automatic execution on load** - Never run code automatically when file is loaded/evaluated; allows use as library
- **Implement example methods** - Create one or more `example` methods that demonstrate usage with default parameters

**Function Design:**
- **Separate concerns by function level:**
  - Low-level: Individual component creation (e.g., `create_table_leg`, `create_table_top`)
  - Mid-level: Composite operations (e.g., `create_table_legs` - creates all four legs)
  - High-level: Complete assemblies (e.g., `create_simple_table`)
  - Orchestration: Example methods with transaction management (`example`)
- **Transaction management only in orchestration** - Only `example` methods (or similar top-level functions) should use `start_operation`/`commit_operation`
- **Parametrize location** - Functions accept `entities` as "where" parameter for flexible placement
- **Return created objects** - Functions return created groups/entities for further manipulation
- **Document all public functions** - Use YARD comments with `@param` and `@return` tags

**Example Structure:**
```ruby
module SupexBasicTable
  def self.create_table_leg(...) # Low-level
    # Creates single leg, returns group
  end

  def self.create_table_legs(...) # Mid-level
    # Creates all legs using create_table_leg
  end

  def self.create_simple_table(...) # High-level
    # Assembles complete table
  end

  def self.example # Orchestration
    # Transaction management here
    model.start_operation('Create Table', true)
    begin
      create_simple_table(...)
      model.commit_operation
    rescue
      model.abort_operation
      raise
    end
  end
end
```

## Modifying the Example

When editing scripts:
1. Edit the Ruby file in your IDE (full syntax highlighting available)
2. Re-run the script using `eval_ruby_file`
3. Use introspection tools to verify changes
4. Iterate as needed

Scripts are version controlled with git, making it easy to track changes and collaborate.
