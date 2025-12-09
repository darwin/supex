# Extended Workflow Examples

Extended examples and reference material. For essential patterns, see `prompt.md`.

## Common Geometry Operations

```ruby
# Create face and extrude
face = entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
face.pushpull(50.cm)

# Create group with geometry
group = entities.add_group
group.entities.add_face(...)

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

## Materials

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

## Components

```ruby
# Create component definition
definition = model.definitions.add('MyComponent')
definition.entities.add_face(...)

# Place instance
instance = entities.add_instance(definition, transformation)
instance.name = 'Instance 1'

# Access definition from instance
instance.definition.entities.each { |e| ... }
```

## Curves and Arcs

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

## Layers/Tags

```ruby
# Create layer
layer = model.layers.add('My Layer')

# Assign to entity
group.layer = layer

# Hide layer
layer.visible = false
```

## Selection and Iteration

```ruby
# Get selection
selection = model.selection
selection.each { |entity| ... }

# Filter by type
groups = entities.grep(Sketchup::Group)
faces = entities.grep(Sketchup::Face)

# Find by name
table = entities.find { |e| e.respond_to?(:name) && e.name == 'Table' }

# Find by attribute
tagged = entities.select { |e| e.get_attribute('supex', 'type') == 'my_tag' }
```

## Bounding Box

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

## Units and Conversions

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

## Error Handling Patterns

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

## Debugging Tips

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
