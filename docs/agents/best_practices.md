# Modeling Best Practices

Lessons learned from real SketchUp modeling projects. For code patterns and workflow, see the main prompt.

## Profile-First Geometry

Build 3D shapes by extruding 2D profiles rather than complex boolean operations:

```ruby
# Good: Draw profile, then extrude
profile = entities.add_face(profile_points)
profile.pushpull(depth)

# Avoid: Complex 3D boolean operations
# They often create broken geometry or unexpected results
```

## Pushpull Direction

Face normals determine pushpull direction. If pushpull goes the wrong way:

```ruby
# Check/flip normal before pushpull
face.reverse! if face.normal.z < 0

# Or use negative value
face.pushpull(-depth)  # Extrude in opposite direction
```

## Edge Treatment for Realism

Real objects have slightly rounded edges. For clean geometry:

- **Chamfer in profile** - Add angled corners to 2D profile before extrusion
- **Octagonal sections** - For fully rounded rectangular parts, use 8-sided profile
- **Avoid complex fillets** - SketchUp fillets often create overlapping/broken geometry

```ruby
# Instead of sharp corner [0,0], [1,0], [0,1]
# Use chamfered corner [0,0.1], [0.1,0], [1,0], [0,1]
```

## Material Timing

Apply materials after geometry is verified:

1. Create all geometry first
2. Verify with `list_entities` or `take_screenshot`
3. Apply materials only after structure is correct

Materials on broken geometry are wasted effort.

## Common Pitfalls

- **Coplanar faces** - Faces on same plane merge unexpectedly. Offset by 0.1.mm
- **Tiny edges** - Edges < 1mm can cause issues. Use reasonable minimums
- **Reversed faces** - Back faces (blue) showing means normals are wrong
- **Stray edges** - Leftover edges break face creation. Clean up with `entities.grep(Sketchup::Edge)`
