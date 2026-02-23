# AGENTS.md

## Project Overview

Example project demonstrating the Supex workflow for SketchUp automation. Creates a simple wooden table with four legs using modular Ruby scripts.

## Project Structure

```
example-simple-table/
├── src/                  # Ruby scripts (module SupexSimpleTable)
│   ├── helpers.rb        # Shared utilities, constants, cleanup
│   ├── create_table.rb   # Table creation (top + legs)
│   ├── add_decorations.rb # Decorative trim for edges
│   ├── add_vase.rb       # Ceramic vase (Follow Me revolution)
│   └── sketchup_extensions.rb # Chainable Group extensions
├── supex-guide/          # Symlink to supex docs/agents/guide/
├── playground/           # Experimental space for VCAD modeling
└── .tmp/                 # Temporary files (gitignored)
```

## Git Conventions

- Commit messages in English
- Imperative mood, capitalized first letter, no trailing period
- Example: `Add decorative trim to table edges`
- Remote `origin` exists (orphan branch of `darwin/supex`)

## SketchUp Modeling with Supex

For modeling guidance, workflow rules, and tool reference see `supex-guide/` (start with `supex-guide/README.md`).

## Ruby Conventions

- 2-space indentation, `frozen_string_literal: true` on every file
- All scripts reopen `module SupexSimpleTable` to add their functions
- Dependencies via `require_relative` at the top of each file (no auto-require)
- Low-level functions create geometry; `example_*` functions handle transactions, cleanup, and error recovery
- Idempotence via attribute-based tagging (`ATTR_DICT`/`ATTR_KEY` constants in `helpers.rb`)
- YARD documentation (`@param`, `@return`) on public methods

## Project Scripts

Each script loads its own dependencies via `require_relative`:

| Script | Requires | Provides |
|--------|----------|----------|
| `src/helpers.rb` | (none) | Module definition, constants, cleanup utilities |
| `src/create_table.rb` | helpers, sketchup_extensions | `example_table` (returns table group) |
| `src/add_decorations.rb` | helpers, sketchup_extensions | `example_decorations` |
| `src/add_vase.rb` | helpers | `example_vase` |
| `src/sketchup_extensions.rb` | (none) | Chainable `.move_to`, `.rotate` on Group |

## Running the Examples

File paths are relative to the project root (workspace directory).

```ruby
# Load the main script (pulls in helpers.rb + sketchup_extensions.rb via require_relative)
eval_ruby_file('src/create_table.rb')

# Create table — returns the table group for further use
table = SupexSimpleTable.example_table

# For decorations or vase individually, load their scripts first
eval_ruby_file('src/add_decorations.rb')
SupexSimpleTable.example_decorations

eval_ruby_file('src/add_vase.rb')
SupexSimpleTable.example_vase

# Or create full setup in one call (loads all scripts automatically)
SupexSimpleTable.example_full
```

## Verification Commands

```ruby
# Get model statistics
get_model_info()

# List entities by type
list_entities('groups')

# Get table group from model (find by name)
table = Sketchup.active_model.entities.find { |e| e.is_a?(Sketchup::Group) && e.name == 'Simple Table' }

# Verify table structure
SupexSimpleTable.verify_table(table)

# Get table dimensions
SupexSimpleTable.describe_table(table)

# Take screenshots from multiple angles
take_batch_screenshots(shots: [
  { camera: { type: 'standard_view', view: 'iso' } }
])
```
