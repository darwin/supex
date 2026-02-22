# Modeling Best Practices

Operational guardrails from real SketchUp + VCAD projects.

For source-of-truth behavior, see `supex-guide/README.md`.

## Choose the Right Workflow First

- Use the Ruby workflow for SketchUp-native operations (editing existing entities, tags/materials, camera, metadata)
- Use the VCAD workflow for repeatable parametric solids authored in `.skp.oo`
- In mixed tasks, keep geometry authoring in VCAD and use Ruby for post-placement organization

## VCAD CAD Library Reuse

- Inspect existing project `.oo` modules before writing new geometry logic
- Prefer existing exported helpers from the CAD library
- Keep `.skp.oo` files thin: compose parameters and library calls
- Do not invent unsupported primitives or custom DSL forms

## VCAD Import Rules

- `[import ...]` is supported in all VCAD tools — imports are auto-detected and resolved
- Keep `[import ...]` declarations in `.skp.oo` files (or inline code) only
- Do not put `[import ...]` in `.oo` modules loaded via `[use ...]`

## VCAD Update Safety

- Keep `node_id` stable to preserve predictable updates
- Use `vcad_update` for isolated node changes
- Use `vcad_update_cascade` when dependencies exist
- Use `vcad_watch_pause` / `vcad_watch_resume` while editing multiple VCAD files

## VCAD Geometry Constraints

- One `.skp.oo` file must evaluate to one solid
- Prefer BRep-on-BRep booleans for reliable CSG behavior
- Mixed native-mesh + BRep booleans can have limitations; verify with `vcad_list_nodes` and screenshots
- Validate results with `vcad_list_nodes` and screenshots after each update

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

**Apply materials to Groups/Components only** - never to raw faces/edges unless the user explicitly requests it. Materials on containers are cleaner and easier to manage.

## Visual Debugging with Batch Screenshots

When developing and testing geometry-creating code, use `take_batch_screenshots` for comprehensive visual verification:

**Best practices:**

1. **Isolate the target** - Use the `isolate` parameter to show only the component/group being worked on
2. **Multiple angles** - Capture several views to verify geometry from all sides
3. **Use isometric view** - The `iso` view uses parallel projection (no perspective), ideal for verifying proportions

**Recommended shot set:**

```ruby
take_batch_screenshots(
  shots=[
    {"camera": {"type": "standard_view", "view": "front"}, "name": "front"},
    {"camera": {"type": "standard_view", "view": "right"}, "name": "right"},
    {"camera": {"type": "standard_view", "view": "top"}, "name": "top"},
    {"camera": {"type": "standard_view", "view": "iso"}, "name": "iso"}
  ],
  isolate=entity_id  # ID of the group/component being developed
)
```

**Available standard views:** `top`, `bottom`, `front`, `back`, `left`, `right`, `iso`

All standard views use parallel projection - no perspective distortion.

## Components for Repeated Geometry

When creating objects with identical repeated parts, use components and instances rather than duplicating geometry:

```ruby
# Good: Create component definition, then place instances
leg_def = model.definitions.add("Table Leg")
leg_entities = leg_def.entities
# Build leg geometry once in leg_entities...

# Place 4 instances at different positions
positions = [
  Geom::Transformation.new([0, 0, 0]),
  Geom::Transformation.new([width, 0, 0]),
  Geom::Transformation.new([width, depth, 0]),
  Geom::Transformation.new([0, depth, 0])
]
positions.each { |t| entities.add_instance(leg_def, t) }

# Bad: Creating 4 separate groups with identical geometry
# - Wastes file size
# - Cannot edit all legs at once
# - No semantic relationship between parts
```

**When to use components:**

- **Table/chair legs** - 4 identical legs should be 4 instances
- **Window frames** - Same window used multiple times
- **Railings/balusters** - Repeated vertical elements
- **Hardware** - Screws, handles, hinges
- **Any identical repeated element**

**Benefits:**

- **Smaller file size** - Geometry stored once, referenced multiple times
- **Edit all at once** - Change the definition, all instances update
- **Organization** - Clear semantic structure in the model
- **Replace easily** - Swap component definition to change all instances

## Common Pitfalls

- **Coplanar faces** - Faces on same plane merge unexpectedly. Offset by 0.1 mm
- **Tiny edges** - Edges < 1mm can cause issues. Use reasonable minimums
- **Reversed faces** - Back faces (blue) showing means normals are wrong
- **Stray edges** - Leftover edges break face creation. Clean up with `entities.grep(Sketchup::Edge)`
