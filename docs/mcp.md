# MCP Reference

MCP tools available for AI agents (via Claude Code).

## Ruby Execution

| Tool | Description |
|------|-------------|
| `eval_ruby` | Execute Ruby code directly |
| `eval_ruby_file` | Execute Ruby script from file (recommended) |

## Model Introspection

| Tool | Description |
|------|-------------|
| `get_model_info` | Get entity counts, units, modified state |
| `list_entities` | List entities with filtering by type |
| `get_selection` | Get currently selected entities |
| `get_layers` | List all layers/tags with visibility |
| `get_materials` | List all materials with colors |
| `get_camera_info` | Get camera position and settings |

## Visualization

| Tool | Description |
|------|-------------|
| `take_screenshot` | Capture view to PNG (returns file path) |
| `take_batch_screenshots` | Take multiple screenshots with different camera positions |

### take_batch_screenshots

Take multiple screenshots with different camera positions in a single batch. Zero visual flicker - renders offscreen while preserving user's view.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `shots` | list | required | List of shot specifications (see below) |
| `output_dir` | string | auto | Output directory (defaults to `.tmp/batch_screenshots/timestamp/`) |
| `base_name` | string | `"screenshot"` | Base filename for screenshots |
| `width` | int | 1920 | Default width for all shots |
| `height` | int | 1080 | Default height for all shots |
| `transparent` | bool | false | Use transparent background |
| `restore_camera` | bool | true | Restore original camera after batch |

**Shot specification:**

Each shot in the `shots` array is a dict with:
- `camera`: Camera specification (see camera types below)
- `name`: Optional custom name for the shot (used in filename)
- `width`/`height`: Optional per-shot size override
- `isolate`: Optional entity_id to isolate (shows only that subtree)

**Camera types:**

| Type | Parameters | Description |
|------|------------|-------------|
| `standard_view` | `view`: top/front/right/left/back/bottom/iso | Standard orthographic views |
| `custom` | `eye`, `target`, optional `up`/`fov`/`perspective` | Custom camera position |
| `zoom_entity` | `entity_ids`, optional `padding` | Zoom to fit specific entities |

All camera types support `zoom_extents` boolean (default true) - when true, auto-adjusts camera to fit visible content.

**Example:**
```json
{
  "shots": [
    {"camera": {"type": "standard_view", "view": "front"}, "name": "front"},
    {"camera": {"type": "standard_view", "view": "iso"}, "name": "overview"},
    {"camera": {"type": "custom", "eye": [100,100,100], "target": [0,0,0], "zoom_extents": false}},
    {"camera": {"type": "standard_view", "view": "top"}, "isolate": 12345, "name": "detail"}
  ]
}
```

## Model Management

| Tool | Description |
|------|-------------|
| `open_model` | Open .skp file by path |
| `save_model` | Save current model |
| `export_scene` | Export to skp/obj/stl/png/jpg |

## Status

| Tool | Description |
|------|-------------|
| `check_sketchup_status` | Verify connection health |
| `console_capture_status` | Get Ruby console logging info |
