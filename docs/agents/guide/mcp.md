# MCP Reference

Canonical MCP tool inventory for Supex.

Source of truth in code:

- `driver/src/supex_driver/mcp/mcp_server.py`
- `driver/src/supex_driver/mcp/vcad_tools.py`
- `driver/src/supex_driver/mcp/vcad_diagnostics.py`

Note: `reload_extension` is a CLI command (`./supex reload`), not an MCP tool.

## Core Status

| Tool | Description |
|------|-------------|
| `check_sketchup_status` | Check SketchUp bridge connectivity and version |
| `console_capture_status` | Show runtime console capture status/log path |

## Ruby Execution

| Tool | Description |
|------|-------------|
| `eval_ruby` | Execute inline Ruby code |
| `eval_ruby_file` | Execute Ruby from file path |

## Model Introspection

| Tool | Description |
|------|-------------|
| `get_model_info` | Model title, units, entity counts, modified state |
| `list_entities` | List entities with optional type filter |
| `get_selection` | List selected entities |
| `get_layers` | List layers/tags |
| `get_materials` | List materials |
| `get_camera_info` | Current camera info |

## Visualization

| Tool | Description |
|------|-------------|
| `take_screenshot` | Capture SketchUp view to PNG (returns file path) |
| `take_batch_screenshots` | Capture multiple camera shots in one batch |

## Model Management

| Tool | Description |
|------|-------------|
| `open_model` | Open `.skp` model by absolute path |
| `save_model` | Save current model (optionally to path) |
| `export_scene` | Export scene (`skp`, `obj`, `stl`, `png`, `jpg`, `jpeg`) |

## VCAD Authoring

For full workflow and semantics, see [VCAD Integration](vcad.md).

| Tool | Description |
|------|-------------|
| `vcad_place` | Evaluate `.cmp.oo` and place/update node in SketchUp (imports auto-resolved) |
| `vcad_update` | Re-evaluate a single node |
| `vcad_update_cascade` | Re-evaluate node and downstream dependents in DAG order |
| `vcad_inspect` | Evaluate and return geometry metadata |
| `vcad_eval` | REPL-like Loon evaluation |
| `vcad_list_nodes` | List VCAD nodes present in the model |
| `vcad_watch_pause` | Pause reactive watch processing |
| `vcad_watch_resume` | Resume and flush accumulated watch events |
| `vcad_export` | Sidecar export API surface (treat as experimental until fully wired end-to-end) |

## VCAD Viewer Relay

| Tool | Description |
|------|-------------|
| `vcad_viewer_state` | Get viewer state snapshot |
| `vcad_viewer_screenshot` | Save viewer screenshot to `.tmp/vcad-viewer/` |
| `vcad_viewer_focus` | Focus viewer camera on a node |

## VCAD Diagnostics

| Tool | Description |
|------|-------------|
| `vcad_health` | Liveness/readiness and negotiated capability summary |
| `vcad_metrics` | Operational telemetry snapshot |
| `vcad_reconcile_status` | Last reconciliation run state |
