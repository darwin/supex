## SketchUp Modeling with Supex

This project uses Supex for SketchUp automation.

### Documentation

Documentation is available in this directory:

1. `workflow.md` - Complete workflow guide
2. `best_practices.md` - Geometry lessons and pitfalls
3. `quick_reference.md` - Quick lookup for common classes
4. `api/` - SketchUp API documentation (e.g., `api/Sketchup/Face.md`)

### When to Read What

| Situation | Read |
|-----------|------|
| Starting a modeling task | `workflow.md` |
| Geometry not working as expected | `best_practices.md` |
| Need method signatures | `api/Sketchup/Face.md` |
| Searching for a class | `api/INDEX.md` |

### Workflow

1. Write Ruby scripts in your project's `src/` directory
2. Execute with `eval_ruby_file(path)` - provides proper error reporting
3. Verify with `get_model_info()`, `take_screenshot()`, `list_entities()`
4. Iterate until correct

### Conventions

- Wrap operations in `model.start_operation('Name', true)` / `commit_operation`
- Organize geometry in groups/components with descriptive names
- Use `frozen_string_literal: true` in all Ruby files
- Implement idempotence - scripts should be safe to re-run

### Script Organization

Recommended structure:
- `src/helpers.rb` - Reusable utility functions
- `src/main.rb` - Main entry point or orchestration
- `src/*.rb` - Feature-specific scripts

### Error Handling

Always handle errors gracefully:
```ruby
begin
  model.start_operation('My Operation', true)
  # ... geometry code ...
  model.commit_operation
rescue => e
  model.abort_operation
  raise e
end
```

### Interactive Examples (REPL)

Use `if false` block at the end of each script for interactive examples:
```ruby
if false # rubocop:disable Lint/LiteralAsCondition
  MyModule.example_function
  MyModule.another_example
end
```

This pattern (similar to Clojure's `(comment ...)` block):
- Never executes during `eval_ruby_file`
- Preserves syntax highlighting in IDE
- Allows sending individual lines to REPL for testing
- Rubocop ignores the literal condition with inline disable

### Essential Classes

**Modeling**
- `api/Sketchup/Model.md` - Main model object, entry point
- `api/Sketchup/Entities.md` - Collection of entities, add geometry here
- `api/Sketchup/Face.md` - Faces with pushpull, materials
- `api/Sketchup/Edge.md` - Edges connecting vertices
- `api/Sketchup/Group.md` - Grouped entities for organization

**Geometry Math**
- `api/Geom/Point3d.md` - 3D points
- `api/Geom/Vector3d.md` - 3D vectors
- `api/Geom/Transformation.md` - Transformations (move, rotate, scale)
- `api/Geom/BoundingBox.md` - Bounding boxes

**Organization**
- `api/Sketchup/ComponentDefinition.md` - Component definitions
- `api/Sketchup/ComponentInstance.md` - Component instances
- `api/Sketchup/Layer.md` - Layers/tags
- `api/Sketchup/Material.md` - Materials and colors
