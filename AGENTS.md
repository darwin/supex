# AGENTS.md

## Project Overview

Example project demonstrating the Supex workflow for SketchUp automation. Creates a simple wooden table with four legs using modular Ruby scripts.

## SketchUp Modeling with Supex

@supex-docs/prompt.md

### Project Scripts

- `src/helpers.rb` - Shared utilities (cleanup, validation, material handling)
- `src/create_table.rb` - Table creation with top and legs
- `src/add_decorations.rb` - Decorative trim for table edges
- `src/add_vase.rb` - Ceramic vase using Follow Me (revolution)
- `src/sketchup_extensions.rb` - Chainable extensions for Sketchup::Group

All scripts use `module SupexSimpleTable` - call functions as `SupexSimpleTable.method_name()`.

### Running the Examples

```ruby
# Load scripts first
eval_ruby_file('src/create_table.rb')

# Create table only (idempotent)
SupexSimpleTable.example_table

# Add decorative trim to existing table
SupexSimpleTable.example_decorations

# Add vase on table
SupexSimpleTable.example_vase

# Or create full setup in one call
SupexSimpleTable.example_full
```

### Verification Commands

```ruby
# Get model statistics
get_model_info()

# List entities by type
list_entities('groups')

# Verify table structure
SupexSimpleTable.verify_table(table)

# Get table dimensions
SupexSimpleTable.describe_table(table)

# Take screenshots from multiple angles
take_batch_screenshots(shots: [
  { camera: { type: 'standard_view', view: 'iso' } }
])
```
