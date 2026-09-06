# Workflow Reference

General patterns applicable to both Ruby and VCAD workflows.

For workflow-specific rules and snippets, see `ruby.md` and `vcad.md`.

## Workflow Chooser

| Goal | Primary workflow | Why |
|------|------------------|-----|
| Manipulate existing SketchUp entities and settings | Ruby | Direct SketchUp API control |
| Build repeatable parametric solids from source | VCAD | `.cmp.oo` source-of-truth and deterministic updates |
| Drive geometry from host entity imports | VCAD | Use `[import ...]` in `.cmp.oo` source — auto-resolved |

## Visual Debugging with Batch Screenshots

Use `take_batch_screenshots` for comprehensive geometry verification in both workflows:

1. **Isolate the target** - Set the per-shot `isolate` key (entity ID of a group/component) to show only the subtree being worked on
2. **Multiple angles** - Capture several views to verify geometry from all sides
3. **Use isometric view** - The `iso` view uses parallel projection, ideal for verifying proportions

```ruby
take_batch_screenshots(
  shots=[
    {"camera": {"type": "standard_view", "view": "front"}, "name": "front", "isolate": entity_id},
    {"camera": {"type": "standard_view", "view": "right"}, "name": "right", "isolate": entity_id},
    {"camera": {"type": "standard_view", "view": "top"}, "name": "top", "isolate": entity_id},
    {"camera": {"type": "standard_view", "view": "iso"}, "name": "iso", "isolate": entity_id}
  ]
)
```

`isolate` is a key inside each shot, not a top-level argument; `entity_id` is the ID of the group/component being developed. Shots without it render the whole model.

Available standard views: `top`, `bottom`, `front`, `back`, `left`, `right`, `iso` — all use parallel projection.
