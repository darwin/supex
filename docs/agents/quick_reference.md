# Quick Reference

**Most Used Classes:**
- `Sketchup::Model` - The active model (entry point for all operations)
- `Sketchup::Entities` - Entity collection (add geometry here)
- `Sketchup::Face` / `Sketchup::Edge` - Basic geometry primitives
- `Geom::Point3d` / `Geom::Vector3d` - 3D coordinates and directions
- `Geom::Transformation` - Positioning and scaling

**Common Entry Points:**
```ruby
model = Sketchup.active_model        # Get active model
entities = model.active_entities     # Get entities collection
selection = model.selection          # Get selected entities
```
