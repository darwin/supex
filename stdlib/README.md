# Supex Standard Library

A shared library of utility functions for SketchUp, available to both AI agents and human developers.

## Installation

The stdlib is loaded automatically when SupexRuntime starts. No manual installation required.

To use a custom stdlib location, set the `SUPEX_STDLIB_PATH` environment variable.

## Usage

### Utils.tree

Visualize SketchUp entity hierarchy in a tree format (similar to unix `tree` command):

```ruby
puts SupexStdlib::Utils.tree
```

Output:
```
.
|-- [Group] Table
|   |-- [Group] Legs
|   `-- [Group] Top
`-- [ComponentInstance] Chair
```

#### Options

```ruby
# Limit depth
puts SupexStdlib::Utils.tree(nil, max_depth: 2)

# Show entity IDs
puts SupexStdlib::Utils.tree(nil, show_ids: true)

# Include hidden entities
puts SupexStdlib::Utils.tree(nil, show_hidden: true)

# Hide type labels
puts SupexStdlib::Utils.tree(nil, show_types: false)

# Filter to specific types
puts SupexStdlib::Utils.tree(nil, types: ['Group'])

# Start from specific entity
group = Sketchup.active_model.entities.grep(Sketchup::Group).first
puts SupexStdlib::Utils.tree(group)
```

## Development

```bash
# Run linter
rake rubocop

# Generate documentation
rake yard
```
