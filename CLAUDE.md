# CLAUDE.md

## Project Overview

Example project demonstrating the Supex workflow for SketchUp automation. Creates a simple wooden table with four legs using modular Ruby scripts.

## SketchUp Modeling with Supex

This project uses Supex MCP for SketchUp automation.

### Documentation

Read MCP resources for SketchUp API documentation:

1. `supex://docs/index` - Start here, lists all available resources
2. `supex://docs/workflow` - Complete workflow guide
3. `supex://docs/best-practices` - Geometry lessons and pitfalls
4. `supex://docs/api/Sketchup/Face` - API docs for specific classes

### Project Scripts

- `scripts/helpers.rb` - Shared utilities (cleanup, common operations)
- `scripts/create_table.rb` - Creates a basic wooden table with four legs

All scripts use `module SupexSimpleTable` - call functions as `SupexSimpleTable.method_name()`.

### Workflow

1. Write Ruby scripts in `scripts/` directory
2. Execute with `eval_ruby_file(path)`
3. Verify with `get_model_info()`, `take_screenshot()`
4. Iterate until correct

### Running the Example

```ruby
# Execute the table creation script
eval_ruby_file('scripts/create_table.rb')

# Run the example (idempotent - safe to run multiple times)
SupexSimpleTable.example_table
```
