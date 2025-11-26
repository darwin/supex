## SketchUp Modeling with Supex

This project uses Supex MCP for SketchUp automation.

### Documentation

Read MCP resources for SketchUp API documentation:

1. `supex://docs/index` - Start here, lists all available resources
2. `supex://docs/workflow` - Complete workflow guide
3. `supex://docs/best-practices` - Geometry lessons and pitfalls
4. `supex://docs/api/Sketchup::Face` - API docs for specific classes (use Ruby `::` syntax)

### Workflow

1. Write Ruby scripts in your project
2. Execute with `eval_ruby_file(path)`
3. Verify with `get_model_info()`, `take_screenshot()`
4. Iterate until correct

### Conventions

- Use metric units (meters, centimeters)
- Wrap operations in `model.start_operation` / `commit_operation`
- Organize geometry in groups/components
