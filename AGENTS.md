# AGENTS.md

## Project Overview

Example project demonstrating the Supex workflow for SketchUp automation. Creates a simple wooden table with four legs using modular Ruby scripts.

## SketchUp Modeling with Supex

@supex-docs/prompt.md

### Project Scripts

- `src/helpers.rb` - Shared utilities (cleanup, common operations)
- `src/create_table.rb` - Creates a basic wooden table with four legs

All scripts use `module SupexSimpleTable` - call functions as `SupexSimpleTable.method_name()`.

### Running the Example

```ruby
# Execute the table creation script
eval_ruby_file('src/create_table.rb')

# Run the example (idempotent - safe to run multiple times)
SupexSimpleTable.example_table
```
