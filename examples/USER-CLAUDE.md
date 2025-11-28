## SketchUp Modeling with Supex

This project uses Supex MCP for SketchUp automation.

### Documentation

Read MCP resources for SketchUp API documentation:

1. `supex://docs/INDEX` - Start here, lists all available resources
2. `supex://docs/workflow` - Complete workflow guide
3. `supex://docs/best-practices` - Geometry lessons and pitfalls
4. `supex://docs/quick-reference` - Quick lookup for common classes
5. `supex://docs/api/{class}` - API docs using Ruby syntax (e.g., `supex://docs/api/Sketchup::Face`)

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
