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

## Model Management

| Tool | Description |
|------|-------------|
| `open_model` | Open .skp file by path |
| `save_model` | Save current model |
| `export_scene` | Export to various formats |

## Status

| Tool | Description |
|------|-------------|
| `check_sketchup_status` | Verify connection health |
| `console_capture_status` | Get Ruby console logging info |
