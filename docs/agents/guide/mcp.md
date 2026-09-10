# MCP Reference

Canonical MCP tool inventory for Supex.

Source of truth: the tool registrations in the supex driver's `mcp` package (`mcp_server.py`, `vcad_tools.py`, `vcad_diagnostics.py`); a driver test keeps this inventory in sync with them.

Note: `reload_extension` is a CLI command (`./supex reload`), not an MCP tool.

## Core Status

| Tool | Description |
|------|-------------|
| `check_status` | Unified health check: SketchUp bridge, console capture, VCAD sidecar, VCAD viewer; `sketchup.transport` shows the effective timeout, retries, replay rule and expected model |

## Ruby Execution

| Tool | Description |
|------|-------------|
| `eval_ruby` | Execute inline Ruby code |
| `eval_ruby_file` | Execute Ruby from file path |

Both accept an optional `expected_model_path`: the runtime refuses to run the code unless that `.skp` file is the active model. `SUPEX_EXPECTED_MODEL` applies the same guard to every model-bound tool. A request that was sent but got no response is not replayed; the result then carries `error_type: "unknown_result"` and the model must be inspected before running the code again (see `troubleshooting.md`).

## Model Introspection

| Tool | Description |
|------|-------------|
| `get_model_info` | Model title, units, entity counts, modified state |
| `list_entities` | List entities with optional type filter |
| `get_entity` | Full state of one entity by ID: bounds, dimensions, layer, material, flags; transformation and definition for groups/instances |
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
| `open_model` | Open `.skp` model by path (relative paths resolve against the workspace) |
| `save_model` | Save current model (optionally to path); `expected_model_path` refuses to save another document |
| `export_scene` | Export scene (`skp`, `obj`, `stl`, `png`, `jpg`, `jpeg`) |

## VCAD Authoring

For full workflow and semantics, see [VCAD Integration](vcad.md).

| Tool | Description |
|------|-------------|
| `vcad_place` | Evaluate `.cmp.oo` and place/update node in SketchUp (imports auto-resolved) |
| `vcad_update` | Re-evaluate node; with `cascade=true` also updates downstream dependents in DAG order |
| `vcad_inspect` | Evaluate and return geometry metadata |
| `vcad_eval` | REPL-like Loon evaluation |
| `vcad_list_nodes` | List VCAD nodes present in the model |
| `vcad_watch_pause` | Pause reactive watch processing |
| `vcad_watch_resume` | Resume and flush accumulated watch events |

## VCAD Viewer Relay

| Tool | Description |
|------|-------------|
| `vcad_viewer_state` | Get viewer state snapshot |
| `vcad_viewer_screenshot` | Save viewer screenshot to `.tmp/vcad-viewer/` |
| `vcad_viewer_focus` | Focus viewer camera on a node |

## VCAD Diagnostics

| Tool | Description |
|------|-------------|
| `vcad_metrics` | Operational telemetry snapshot |
| `vcad_reconcile_status` | Last reconciliation run state |
