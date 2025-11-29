# Modeling Best Practices (Lessons Learned)

## Coordinate System Awareness
- X-axis (red) = right, Y-axis (green) = forward, Z-axis (blue) = up
- Always verify orientation - handles should extend along X-axis, not Z-axis
- Test geometry orientation early in modeling process

## Scene Structure and Naming is Critical
- ALWAYS create named groups/components for ALL geometry - never leave loose entities
- Without proper groups, Outliner shows empty and models become unmanageable
- Use descriptive names that clearly identify each part (e.g., "3D Heart", "Table Leg Front Left")
- Group ALL entities immediately after creation: `entities.add_group(entities.to_a)`
- Set meaningful names: `group.name = "Descriptive Name"`
- Apply materials to groups/faces, not loose geometry
- Proper scene organization is essential for professional workflows

## Edge Treatment and Realism
- Real objects rarely have perfectly sharp edges
- Use chamfered profiles instead of complex fillets for clean geometry
- Create octagonal cross-sections for fully chamfered rectangular parts
- Avoid complex fillet operations that create overlapping geometry

## Geometry Creation Strategy
- Start with simple profiles and extrude rather than complex 3D operations
- Use pushpull operations carefully - verify direction (positive vs negative)
- For rounded edges: chamfer corners in the profile, then extrude
- Test each major step to catch orientation/connection issues early

## Iterative Development
- Build models incrementally with frequent testing
- Create separate groups for each logical component
- Apply materials after geometry is complete and verified
- Use descriptive names for groups to aid in debugging
