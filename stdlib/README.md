# Supex Standard Library

A shared library of utility functions for SketchUp, available to both AI agents and human developers.

## Installation

The stdlib is loaded automatically when SupexRuntime starts. No manual installation required.

To use a custom stdlib location, set the `SUPEX_STDLIB_PATH` environment variable.

## Usage

### Shell.tree

Visualize SketchUp entity hierarchy in a tree format (similar to unix `tree` command):

```ruby
puts SupexStdlib::Shell.tree
```

Output (uses Unicode box-drawing characters and type abbreviations):
```
.
├── [G] Table
│   ├── [G] Legs
│   └── [G] Top
└── [C] Chair
```

Type abbreviations: `[G]` = Group, `[C]` = ComponentInstance, `[F]` = Face, `[E]` = Edge

#### Options

```ruby
# Limit depth
puts SupexStdlib::Shell.tree(nil, max_depth: 2)

# Show entity IDs (useful for drill-down)
puts SupexStdlib::Shell.tree(nil, show_ids: true)
# Output: ├── [G] Table (#123)

# Include hidden entities
puts SupexStdlib::Shell.tree(nil, show_hidden: true)

# Hide type labels
puts SupexStdlib::Shell.tree(nil, show_types: false)

# Filter to specific types
puts SupexStdlib::Shell.tree(nil, types: ['Group'])

# Start from specific entity
group = Sketchup.active_model.entities.grep(Sketchup::Group).first
puts SupexStdlib::Shell.tree(group)

# Drill down using entityID (from show_ids output)
puts SupexStdlib::Shell.tree(123, show_ids: true)
# Output:
# [G] Table (#123)
# ├── [G] Legs (#124)
# └── [G] Top (#125)
```

## Development

```bash
# Run linter
rake rubocop

# Generate documentation
rake yard
```
