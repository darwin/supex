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
- **Use helpers.rb for shared utilities** - Place reusable helper functions in `scripts/helpers.rb` with project-specific module
  - Import with `require_relative 'helpers'` at the top of scripts
  - Scripts "reopen" the same module to add their functions (Ruby feature)
  - Prevents code duplication across scripts
  - Use project-specific naming: `module SupexSimpleTable` (prevents conflicts with other Supex projects)
  - All functions accessible as `SupexSimpleTable.method_name(...)`

**Function Design:**
- **Separate concerns by function level:**
  - Low-level: Individual component creation (e.g., `create_table_leg`, `create_table_top`)
  - Mid-level: Composite operations (e.g., `create_table_legs` - creates all four legs)
  - High-level: Complete assemblies (e.g., `create_simple_table`)
  - Orchestration: Example methods with transaction management (`example`)
- **Configuration in orchestration layer** - All configuration values (names, dimensions, metadata, etc.) should be local variables in orchestration functions, not hardcoded in lower-level functions
  - Lower-level functions accept parameters, don't decide values
  - Single source of truth for each configuration value
  - Example: `table_name = 'Table'` and `attribute_type = 'basic_table_example'` in `example`
  - Metadata (attributes, tags) applied in orchestration, not in geometry functions
- **Transaction management only in orchestration** - Only `example` methods (or similar top-level functions) should use `start_operation`/`commit_operation`
- **Parametrize location** - Functions accept `entities` as "where" parameter for flexible placement
- **Return created objects** - Functions return created groups/entities for further manipulation
- **Document all public functions** - Use YARD comments with `@param` and `@return` tags

**Idempotence Pattern:**
- **Example methods MUST be idempotent** - Running example multiple times should produce same result, not duplicate objects
- **Two-tier cleanup approach:**
  1. **Name-based search** (fast) - Find groups by name
  2. **Attribute verification** (precise) - Verify with `get_attribute` to prevent false positives
- **Tag created objects** - Use `set_attribute('supex', 'type', 'module_example')` on created groups
- **Cleanup before create** - Remove previous instances before creating new ones
- **Consistent naming** - Use unique, descriptive names for groups

**Cleanup Helper Pattern:**
Place this in `scripts/helpers.rb` for reuse across scripts:
```ruby
module SupexSimpleTable
  def self.cleanup_by_name_and_attribute(entities, name, attribute_dict, attribute_key, attribute_value)
    entities.grep(Sketchup::Group).each do |group|
      # First filter: name match (fast)
      next unless group.name == name

      # Second filter: attribute verification (precise, prevents false positives)
      group.erase! if group.get_attribute(attribute_dict, attribute_key) == attribute_value
    end
  end
end
```

**Example Structure:**
```ruby
# Import shared helpers (defines module SupexSimpleTable)
require_relative 'helpers'

# Reopen module to add table-specific functions
module SupexSimpleTable

  def self.create_table_leg(...) # Low-level
    # Creates single leg, returns group
  end

  def self.create_table_legs(...) # Mid-level
    # Creates all legs using create_table_leg
  end

  def self.create_simple_table(entities, model, ...) # High-level
    # Assembles complete table - pure geometry function
    # Returns clean object without ANY metadata (orchestration concern)
    main_table = entities.add_group

    # ... create table top and legs ...

    main_table  # Return clean object for orchestration
  end

  def self.example # Orchestration
    model = Sketchup.active_model
    entities = model.entities

    # Configuration (single source of truth)
    table_name = 'Table'
    attribute_type = 'basic_table_example'

    model.start_operation('Create Table', true)
    begin
      # Cleanup previous instances (idempotent)
      cleanup_by_name_and_attribute(entities, table_name, 'supex', 'type', attribute_type)

      # Create clean geometry (no metadata)
      table = create_simple_table(entities, model, ...)

      # Apply ALL metadata together (orchestration concern)
      table.name = table_name
      table.set_attribute('supex', 'type', attribute_type)

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
