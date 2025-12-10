# Supex Standard Library

Utility functions for SketchUp, designed for AI agents.

## Installation

Loaded automatically when SupexRuntime starts. No manual installation required.

## Modules

### Shell

```ruby
# Visualize entity hierarchy (like unix `tree`)
puts SupexStdlib::Shell.tree
# .
# ├── [G] Table
# │   ├── [G] Legs
# │   └── [G] Top
# └── [C] Chair

# Options: max_depth, show_ids, show_hidden, show_types, types
puts SupexStdlib::Shell.tree(nil, max_depth: 2, show_ids: true)

# Drill down by entityID
puts SupexStdlib::Shell.tree(123)
```

### Entity

```ruby
SupexStdlib::Entity.definition(instance)           # Get definition from Group/ComponentInstance
SupexStdlib::Entity.instance?(entity)              # Test if Group or ComponentInstance
SupexStdlib::Entity.swap_definition(inst, new_def) # Swap definition (handles Groups)
SupexStdlib::Entity.copy_attributes(target, src)   # Copy all attribute dictionaries
SupexStdlib::Entity.get_attribute(e, dict, key)    # Get attribute value
SupexStdlib::Entity.set_attribute(e, dict, key, v) # Set attribute value
SupexStdlib::Entity.has_dictionary?(entity, dict)  # Check if dictionary exists
SupexStdlib::Entity.dictionary_names(entity)       # List all dictionary names
```

### Face

```ruby
SupexStdlib::Face.arbitrary_interior_point(face)        # Point inside face
SupexStdlib::Face.includes_point?(face, pt, boundary)   # Test if point in face
SupexStdlib::Face.inner_loops(face)                     # Get hole loops
SupexStdlib::Face.triangulate(face, transformation)     # Get triangles
SupexStdlib::Face.wrapping_face(face)                   # Find containing face
```

### Edge

```ruby
SupexStdlib::Edge.midpoint(edge)           # Get edge midpoint
SupexStdlib::Edge.length(edge)             # Get edge length
SupexStdlib::Edge.direction(edge)          # Get normalized direction
SupexStdlib::Edge.parallel?(edge1, edge2)  # Test if parallel
SupexStdlib::Edge.to_line(edge)            # Convert to [point, vector]
```

### ComponentDefinition

```ruby
SupexStdlib::ComponentDefinition.erase(definition)              # Erase definition and instances
SupexStdlib::ComponentDefinition.place_axes(def, tr, adjust)    # Redefine axes
SupexStdlib::ComponentDefinition.unique_to?(definition, scopes) # Check if unique to scope
```

### Geom

```ruby
SupexStdlib::Geom.mid_point(pt1, pt2)          # Midpoint between points
SupexStdlib::Geom.mid_point(edge)              # Midpoint of edge
SupexStdlib::Geom.offset_points(points, vec)   # Offset array of points
SupexStdlib::Geom.polygon_area(points)         # Polygon area (Newell's method)
SupexStdlib::Geom.polygon_normal(points)       # Polygon normal (Newell's method)
SupexStdlib::Geom.remove_duplicates(array)     # Remove duplicate points/vectors
SupexStdlib::Geom.angle_in_plane(v1, v2, n)    # Angle between vectors (0 to 2pi)
```

### Geom::Transformation

```ruby
SupexStdlib::Geom::Transformation.from_axes(origin, x, y, z)    # Create from axes
SupexStdlib::Geom::Transformation.from_euler_angles(o, x, y, z) # Create from angles
SupexStdlib::Geom::Transformation.euler_angles(tr)              # Extract [x, y, z] angles
SupexStdlib::Geom::Transformation.xaxis(tr)                     # X axis with scale
SupexStdlib::Geom::Transformation.xscale(tr)                    # X scale factor
SupexStdlib::Geom::Transformation.determinant(tr)               # Matrix determinant
SupexStdlib::Geom::Transformation.flipped?(tr)                  # Test if mirrored
SupexStdlib::Geom::Transformation.sheared?(tr)                  # Test if sheared
SupexStdlib::Geom::Transformation.identity?(tr)                 # Test if identity
SupexStdlib::Geom::Transformation.same?(tr1, tr2)               # Compare transformations
SupexStdlib::Geom::Transformation.remove_scaling(tr)            # Remove scaling
SupexStdlib::Geom::Transformation.remove_shearing(tr)           # Make orthogonal
SupexStdlib::Geom::Transformation.transpose(tr)                 # Transpose matrix
```

### Geom::Plane

```ruby
SupexStdlib::Geom::Plane.normal(plane)              # Get unit normal
SupexStdlib::Geom::Plane.point(plane)               # Get point on plane
SupexStdlib::Geom::Plane.parallel?(plane_a, b)      # Test if parallel
SupexStdlib::Geom::Plane.same?(plane_a, b, flip)    # Test if same plane
SupexStdlib::Geom::Plane.transform(plane, tr)       # Transform plane
SupexStdlib::Geom::Plane.valid?(plane)              # Validate plane object
```

### Geom::Point

```ruby
SupexStdlib::Geom::Point.between?(pt, a, b, incl)   # Test if point between two points
SupexStdlib::Geom::Point.front_of_plane?(pt, plane) # Test if in front of plane
```

### Geom::Vector

```ruby
SupexStdlib::Geom::Vector.arbitrary_non_parallel(v)    # Find non-parallel vector
SupexStdlib::Geom::Vector.arbitrary_perpendicular(v)   # Find perpendicular vector
SupexStdlib::Geom::Vector.transform_as_normal(n, tr)   # Transform normal correctly
```

### Geom::BoundingBox

```ruby
bb = SupexStdlib::Geom::BoundingBox.new(points)  # Create from 8 corner points
bb.width, bb.height, bb.depth                     # Dimensions
bb.center, bb.origin                              # Key points
bb.x_axis, bb.y_axis, bb.z_axis                   # Axis vectors
bb.volume, bb.area                                # Measurements
bb.empty?, bb.is_2d?, bb.is_3d?                   # Type checks
```

### Geom::Line

```ruby
line = SupexStdlib::Geom::Line.new(point, vector)  # Create immutable line
line.direction                                      # Normalized direction
line.valid?                                         # Validate line
```

### Color

```ruby
SupexStdlib::Color.grayscale?(color)              # Test if r==g==b
SupexStdlib::Color.luminance(color)               # Perceived brightness (0-255)
SupexStdlib::Color.dark?(color, threshold)        # Test if dark
SupexStdlib::Color.light?(color, threshold)       # Test if light
SupexStdlib::Color.contrast_color(color)          # Get black or white for contrast
SupexStdlib::Color.to_grayscale(color)            # Convert to grayscale [r,g,b]
SupexStdlib::Color.to_hex(color, alpha)           # Convert to "#RRGGBB"
```

### Platform

```ruby
SupexStdlib::Platform.mac?       # Running on macOS?
SupexStdlib::Platform.win?       # Running on Windows?
SupexStdlib::Platform.temp_path  # System temp directory

SupexStdlib::Platform::ID        # "osx64" or "win64"
SupexStdlib::Platform::NAME      # "macOS" or "Windows"
SupexStdlib::Platform::IS_MAC    # Boolean
SupexStdlib::Platform::IS_WIN    # Boolean
```

## Attribution

Adapted from SketchUp community libraries (MIT License):

- **tt-lib** by Thomas Thomassen - https://github.com/thomthom/tt-lib
- **sketchup-community-lib** by Julia Christina Eneroth - https://github.com/Eneroth3/sketchup-community-lib
- **W3C AERT** - Color luminance formula - https://www.w3.org/TR/AERT/#color-contrast

## Development

```bash
bundle exec rake test     # Run tests
bundle exec rake rubocop  # Run linter
bundle exec rake yard     # Generate docs
```
