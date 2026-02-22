# Extended Workflow Examples

Practical playbook for both authoring workflows.

For strict rules and constraints, see `supex-guide/README.md`.

## Workflow Chooser

| Goal | Primary workflow | Why |
|------|------------------|-----|
| Manipulate existing SketchUp entities and settings | Ruby | Direct SketchUp API control |
| Build repeatable parametric solids from source | VCAD | `.skp.oo` source-of-truth and deterministic updates |
| Drive geometry from host entity imports | VCAD | Use `[import ...]` in `.skp.oo` source — auto-resolved |

## VCAD Workflow Loop

1. Check existing `.oo` modules first and reuse CAD library helpers.
2. Keep each `.skp.oo` file as one node that evaluates to exactly one solid.
3. Use `vcad_place` to place nodes (imports are auto-detected and resolved).
5. Re-evaluate with `vcad_update` for one node or `vcad_update_cascade` for dependent graphs.
6. Verify with `vcad_list_nodes()` and screenshots.

### VCAD Node Example

```loon
; skp/bracket.skp.oo
[use shared/params :as p]
[use shared/lib :as lib]

[pipe [lib.base-bracket p.width p.depth p.height]
  [difference
    [translate p.hole_x p.hole_y 0.0
      [cylinder p.hole_radius p.height]]]
  [fillet p.edge_radius]]
```

### VCAD Import Example

```loon
[let host [import :dimensions "entity:12345"]]
[cube [get host :width] 10.0 [get host :height]]
```

`[import ...]` declarations must stay in `.skp.oo` files (or inline code). They do not work in `.oo` modules loaded via `[use ...]`.

### Batch Editing Pattern

```text
vcad_watch_pause()
# edit multiple .skp.oo and .oo files
vcad_watch_resume()  # flushes as one merged cascade update
```

## Ruby Workflow Quick Reference

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

```ruby
# Create component definition
definition = model.definitions.add('MyComponent')
definition.entities.add_face(points)

# Place instance
instance = entities.add_instance(definition, transformation)
instance.name = 'Instance 1'

# Access definition from instance
instance.definition.entities.each { |e| puts e }
```

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
