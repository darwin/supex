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

## Geometry Quality Rules

### Profile-First Geometry

Build 3D shapes by extruding 2D profiles rather than complex boolean operations:

```ruby
# Good: Draw profile, then extrude
profile = entities.add_face(profile_points)
profile.pushpull(depth)

# Avoid: Complex 3D boolean operations
# They often create broken geometry or unexpected results
```

### Pushpull Direction

Face normals determine pushpull direction. If pushpull goes the wrong way:

```ruby
face.reverse! if face.normal.z < 0  # Flip normal before pushpull
face.pushpull(-depth)               # Or use negative value
```

### Edge Treatment for Realism

Real objects have slightly rounded edges. For clean geometry:

- **Chamfer in profile** - Add angled corners to 2D profile before extrusion
- **Octagonal sections** - For fully rounded rectangular parts, use 8-sided profile
- **Avoid complex fillets** - SketchUp fillets often create overlapping/broken geometry

### Material Timing

Apply materials after geometry is verified:

1. Create all geometry first
2. Verify with `list_entities` or `take_screenshot`
3. Apply materials only after structure is correct

Materials on broken geometry are wasted effort.

### Common Pitfalls

- **Coplanar faces** - Faces on same plane merge unexpectedly. Offset by 0.1 mm
- **Tiny edges** - Edges < 1mm can cause issues. Use reasonable minimums
- **Reversed faces** - Back faces (blue) showing means normals are wrong
- **Stray edges** - Leftover edges break face creation. Clean up with `entities.grep(Sketchup::Edge)`

## References

- Extended snippets: `supex-guide/workflow.md`
- SketchUp API: `supex-guide/api/INDEX.md`
- Stdlib reference: `supex-guide/stdlib/README.md`
