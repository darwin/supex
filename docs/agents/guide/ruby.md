# Ruby Workflow Guide

Use this guide when the task is SketchUp-native automation.

## When To Choose Ruby

Use Ruby for:

- editing existing entities, tags/layers, materials, camera, or metadata
- one-off automation that maps directly to SketchUp Ruby API
- operations that do not map cleanly to VCAD constructors

## Workflow Loop

1. Write scripts in the project directory (`.rb` files).
2. Execute with `eval_ruby_file`.
3. Verify with introspection (`get_model_info`, `list_entities`) and screenshots.
4. Iterate by editing the file and re-running.

## Execution Rules

- `eval_ruby_file(path)` - preferred for all non-trivial work (better line numbers and stack traces)
- `eval_ruby(code)` - one-line queries only (`Sketchup.version`, `model.entities.count`)

## Critical Patterns

### 1. Transaction Management (Required)

Always wrap model changes in operations for undo/redo and safe rollback.

```ruby
model = Sketchup.active_model
model.start_operation('Create Object', true)
begin
  # ... geometry/model edits ...
  model.commit_operation
rescue StandardError => e
  model.abort_operation
  puts "Error: #{e.message}"
  raise
end
```

### 2. Organization (Required)

- Group geometry; avoid loose edges/faces in root entities
- Name groups/components for Outliner clarity
- Use components for repeated geometry
- Apply materials to Groups/Components by default

```ruby
group = entities.add_group
group.name = 'Descriptive Name'
# Create geometry inside group.entities, not model.entities
```

### 3. Module Structure

Wrap helpers in a module to avoid namespace collisions.

```ruby
module SupexProjectName
  def self.create_object(entities, params = {})
    # ...
  end

  def self.example_usage
    # Orchestration with transaction management
  end
end
```

Rules:

- no automatic execution when file loads
- use `example_` prefix for orchestration entrypoints

### 4. Standard Library (Prefer Over Custom Helpers)

Check `supex-guide/stdlib/README.md` before writing utility code.

Common modules:

- `SupexStdlib::Geom`
- `SupexStdlib::Geom::Transformation`
- `SupexStdlib::Entity`
- `SupexStdlib::Face`
- `SupexStdlib::Edge`
- `SupexStdlib::Color`
- `SupexStdlib::Shell`

```ruby
mid = SupexStdlib::Geom.mid_point(pt1, pt2)
normal = SupexStdlib::Geom.polygon_normal(points)

if SupexStdlib::Entity.instance?(entity)
  definition = SupexStdlib::Entity.definition(entity)
end
```

Stdlib is loaded automatically (no `require` needed).

### 5. Idempotence Pattern

Example methods should be safe to run repeatedly.

```ruby
def self.example_create
  model = Sketchup.active_model
  entities = model.entities

  object_name = 'My Object'
  attribute_tag = 'my_example'

  model.start_operation('Create Object', true)
  begin
    cleanup_by_name_and_attribute(entities, object_name, 'supex', 'type', attribute_tag)

    obj = create_object(entities)
    obj.name = object_name
    obj.set_attribute('supex', 'type', attribute_tag)

    model.commit_operation
  rescue
    model.abort_operation
    raise
  end
end
```

### 6. Function Hierarchy

Separate low-level part builders from orchestration methods.

```ruby
module SupexProjectName
  def self.create_leg(entities, position, size, height, material)
    # low-level
  end

  def self.create_all_legs(entities, positions, size, height, material)
    # mid-level
  end

  def self.create_table(entities, params = {})
    # high-level pure geometry
  end

  def self.example_table
    # orchestration (transaction + metadata + idempotence)
  end
end
```

### 7. Coordinate System

- X (red) = right
- Y (green) = forward/depth
- Z (blue) = up/height

Verify orientation early; swapped Y/Z is a common error.

## References

- Extended snippets: `supex-guide/workflow.md`
- Geometry QA: `supex-guide/best_practices.md`
- SketchUp API: `supex-guide/api/INDEX.md`
- Stdlib reference: `supex-guide/stdlib/README.md`
