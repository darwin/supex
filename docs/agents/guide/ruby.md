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

## Snippets

### Common Geometry Operations

```ruby
# Create face and extrude
face = entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
face.pushpull(50.cm)

# Create group with geometry
group = entities.add_group
group.entities.add_face(points)

# Transform/move
tr = Geom::Transformation.translation([1.m, 0, 0])
group.transform!(tr)

# Rotation around axis
tr = Geom::Transformation.rotation(ORIGIN, Z_AXIS, 45.degrees)
group.transform!(tr)

# Scale
tr = Geom::Transformation.scaling(2.0)
group.transform!(tr)

# Combined transformation
tr = Geom::Transformation.new(point, xaxis, yaxis, zaxis)
```

### Materials

```ruby
# Create material
material = model.materials.add('Wood')
material.color = Sketchup::Color.new(139, 69, 19)

# Apply to group (preferred)
group.material = material

# Apply to face (only if explicitly needed)
face.material = material

# Texture
material.texture = '/path/to/texture.jpg'
material.texture.size = [1.m, 1.m]
```

### Components

Use components and instances for identical repeated parts (legs, balusters, hardware):

```ruby
# Create component definition once
leg_def = model.definitions.add('Table Leg')
# Build leg geometry once in leg_def.entities...

# Place 4 instances at different positions
positions = [
  Geom::Transformation.new([0, 0, 0]),
  Geom::Transformation.new([width, 0, 0]),
  Geom::Transformation.new([width, depth, 0]),
  Geom::Transformation.new([0, depth, 0])
]
positions.each { |t| entities.add_instance(leg_def, t) }

# Access definition from instance
instance.definition.entities.each { |e| puts e }
```

Benefits: smaller file size, edit-all-at-once, easy replacement via `swap_definition`.

### Curves and Arcs

```ruby
# Arc (center, xaxis, normal, radius, start_angle, end_angle)
edges = entities.add_arc(center, X_AXIS, Z_AXIS, radius, 0, 90.degrees)

# Circle
edges = entities.add_circle(center, Z_AXIS, radius, 24)

# Polygon
edges = entities.add_ngon(center, Z_AXIS, radius, 6)

# Curve from points
edges = entities.add_curve(points_array)
```

### Layers/Tags

```ruby
# Create layer
layer = model.layers.add('My Layer')

# Assign to entity
group.layer = layer

# Hide layer
layer.visible = false
```

### Selection and Iteration

```ruby
# Get selection
selection = model.selection
selection.each { |entity| puts entity }

# Filter by type
groups = entities.grep(Sketchup::Group)
faces = entities.grep(Sketchup::Face)

# Find by name
table = entities.find { |e| e.respond_to?(:name) && e.name == 'Table' }

# Find by attribute
tagged = entities.select { |e| e.get_attribute('supex', 'type') == 'my_tag' }
```

### Bounding Box

```ruby
# Get bounds
bounds = group.bounds

# Properties
bounds.center      # Geom::Point3d
bounds.width       # X dimension
bounds.height      # Z dimension
bounds.depth       # Y dimension
bounds.min         # Corner point
bounds.max         # Corner point
```

### Units and Conversions

```ruby
# Length literals (SketchUp extension)
1.m                # 1 meter
50.cm              # 50 centimeters
25.4.mm            # 25.4 millimeters
1.inch             # 1 inch
1.feet             # 1 foot

# Angle literals
45.degrees         # 45 degrees in radians
Math::PI / 4       # Same as above

# Manual conversion
length_in_inches = length.to_l.to_s  # Returns string with units
```

### Error Handling Patterns

```ruby
# Safe entity access
entity = model.find_entity_by_id(id)
return unless entity
return unless entity.valid?

# Safe face creation (may return nil if edges don't form closed loop)
face = entities.add_face(points)
if face.nil?
  puts "Failed to create face - check points form closed loop"
  return
end

# Check for reversed face
if face.normal.z < 0
  face.reverse!
end
```

### Debugging Tips

```ruby
# Print entity info
puts "Entity: #{entity.class}, ID: #{entity.entityID}"
puts "Bounds: #{entity.bounds.min} to #{entity.bounds.max}" if entity.respond_to?(:bounds)

# Count entities by type
counts = entities.group_by(&:class).transform_values(&:count)
puts counts.inspect

# Verify face validity
face.vertices.each { |v| puts v.position.to_a.inspect }
```

## References

- SketchUp API: `supex-guide/api/INDEX.md`
- Stdlib reference: `supex-guide/stdlib/README.md`
