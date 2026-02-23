# VCAD Integration

VCAD is a BRep (Boundary Representation) kernel integrated into SketchUp via supex. The agent writes parametric CAD code in Loon (a Lisp-like language with algebraic data types), the VCAD Rust sidecar evaluates the code to produce BRep geometry, exports the mesh as DAE, and SketchUp natively imports it as a component.

## Architecture

```
                AI Agent (Claude Code, MCP client)
                             |
                      [MCP Protocol (stdio)]
                             |
                    supex Python MCP Driver
                /            |              \
  [TCP JSON-RPC :9876]  [WebSocket :9878]  [TCP JSON-RPC :9877]
         |                   |                      |
  SketchUp Ruby Runtime  VCAD Viewer        VCAD Rust Sidecar
  (bridge_server.rb)     (Tauri app)        (loon-lang + vcad-eval + vcad-kernel)
         |                                          |
  SketchUp Application                       .cmp.oo files (source of truth)
```

### Evaluation Pipeline

```
.cmp.oo source
    | (loon-lang: parse + interpret)
Value::Adt tree (pure data)
    | (vcad-loon: value_to_document)
vcad_ir::Document (DAG of CsgOp nodes)
    | (vcad-eval: evaluate_document)
vcad_kernel::Solid (BRep geometry)
    | (Solid::to_mesh)
TriangleMesh
    | (DAE export)
.dae file -> SketchUp definitions.import
```

### Components

| Component | Location | Language | Role |
|-----------|----------|----------|------|
| MCP Driver | `driver/src/supex_driver/` | Python | Exposes MCP tools, mediates sidecar and SketchUp |
| VCAD Sidecar | `vcad/sidecar/` | Rust | Evaluates `.cmp.oo` source (tracks `.oo` modules), produces BRep geometry + DAE |
| Ruby Bridge | `runtime/src/supex_runtime/` | Ruby | Imports DAE into SketchUp, manages VCAD nodes |
| Viewer | `vcad/viewer/` | Rust/TypeScript | Standalone Tauri BRep preview |
| Viewer Relay | `driver/src/supex_driver/connection/vcad_viewer_relay.py` | Python | WebSocket bridge (:9878) between MCP driver and viewer |

## Getting Started

### Build the sidecar

```bash
cargo build --release --manifest-path vcad/sidecar/Cargo.toml
```

### Launch for development

```bash
# Start sidecar (builds if needed)
./vcad-sidecar

# Or via the launch script directly
./scripts/launch-vcad-sidecar.sh
```

### Viewer Debugging

The VCAD viewer is a Tauri app (WKWebView on macOS). JavaScript in the Tauri webview cannot be debugged via Chrome DevTools — WKWebView uses WebKit, not Chromium. Use `--dev` to run the viewer frontend as a standalone Vite dev server in the browser instead.

```bash
# Browser debug mode — Vite only, no Tauri window
./scripts/launch-vcad-viewer.sh --dev
```

Open Chrome and navigate to `http://localhost:1420`. Full debugging is available:

- **Chrome DevTools** — Cmd+Option+I (or F12) for JS console, network inspector, DOM inspection
- **Claude Chrome extension** — browser automation and interaction with the viewer page
- **Remote debugging** — launch Chrome with `--remote-debugging-port=9222` to connect external DevTools instances

Note: The Vite dev server serves the same React frontend that Tauri uses. All viewer functionality works identically in the browser, except for Tauri-specific native APIs (which are stubbed or unavailable).

### E2E test flow

1. Start sidecar: `./vcad-sidecar`
2. Start SketchUp with supex runtime: `./scripts/launch-sketchup.sh`
3. Via MCP tools:
   - Create a `.cmp.oo` file with a solid
   - Call `vcad_place("test-bracket", "bracket.cmp.oo")`
   - Verify the component appears: `vcad_list_nodes()`
   - Modify the source file
   - Call `vcad_update("test-bracket")`

## Writing .cmp.oo Files

Each `.cmp.oo` file must produce exactly one solid. The last expression is evaluated and converted to geometry.

### Data model

One `.cmp.oo` file = one SketchUp ComponentDefinition. For multi-part assemblies, use multiple files with shared modules:

```
project/
  AGENTS.md
  README.md
  cmp/
    shared/
      params.oo          # Shared parameters and dimensions
      lib.oo             # Shared helper functions
    base-plate.cmp.oo   # One solid output
    bracket.cmp.oo      # One solid output
```

### Example

```loon
; bracket.cmp.oo
[pipe [cube 50.0 30.0 5.0]
  [difference [cylinder 3.0 10.0]]
  [fillet 1.0]
  [translate 0.0 0.0 10.0]]
```

## Language and API Reference

For Loon language syntax, CAD constructors, and API reference, see the agent documentation:

- **Quick reference**: `docs/agents/guide/README.md` § "Core Loon CAD Constructors"
- **Authoritative source**: `docs/agents/guide/cad-lib/src/lib.loon` — type definitions and constructor signatures

## Import System

VCAD nodes can reference data from existing SketchUp entities using inline `[import ...]` declarations. The driver auto-detects and resolves these references before evaluation. Imports are supported in all VCAD tools (`vcad_place`, `vcad_update`, `vcad_inspect`, `vcad_eval`, `vcad_export`).

**Why imports cannot appear in library modules:** The driver preprocesses `[import ...]` declarations by extracting them from the source, resolving them via SketchUp, and injecting the results before evaluation. Library modules loaded via `[use ...]` bypass this pipeline entirely — the Loon interpreter evaluates them directly. A raw `[import ...]` in a library file will fail at evaluation time because `import` is not a Loon built-in.

### Import syntax

```loon
[let <binding> [import :host "entity:<id>"]]                    ; all data (default)
[let <binding> [import :host "entity:<id>" <extract>]]           ; single extract
[let <binding> [import :host "entity:<id>" <extract> <extract>]] ; multi-extract
```

The first argument after `import` is the **source** keyword (currently only `:host` for SketchUp entities). The second is a source-specific **selector** string. Optional arguments after the selector are **extract** keywords.

### Default import (no extract)

When no extract is specified, returns a map with all available data:

```loon
[let host [import :host "entity:12345"]]
; host => {:dims {:width ... :height ... :depth ...}
;          :bbox {:min [...] :max [...]}
;          :transform {:matrix [...]}}
[cube [get [get host :dims] :width] 10.0 [get [get host :dims] :height]]
```

### Data imports

Extract specific data from SketchUp entities:

| Extract | Binding type | Fields |
|---------|-------------|--------|
| `:dims` | map | `:width`, `:height`, `:depth` (mm) |
| `:bbox` | map | `:min [x,y,z]`, `:max [x,y,z]` (mm) |
| `:transform` | map | `:matrix` (16-element array) |

```loon
; Single extract — returns the data directly
[let host [import :host "entity:12345" :dims]]
[cube [get host :width] 10.0 [get host :height]]

; Multiple extracts — returns a map with requested keys
[let host [import :host "entity:12345" :dims :bbox]]
[cube [get [get host :dims] :width] 10.0 [get [get host :dims] :height]]
```

### Solid imports

Import a solid for CSG composition. Works with both VCAD-backed nodes and native SketchUp solids. `:solid` cannot be combined with other extracts.

```loon
; Import another VCAD node's geometry for boolean operations
[let bracket [import :host "entity:67890" :solid]]
[pipe [cube 100.0 50.0 20.0]
  [difference bracket]]
```

**VCAD-backed entities**: The cached ADT tree is injected directly from the sidecar's ADT cache. The source node must be evaluated first.

**Native SketchUp solids**: Groups and ComponentInstances with face geometry are triangulated in SketchUp and forwarded to the sidecar as `ImportedMesh` ADT values.

### Import resolution flow

```
.cmp.oo source with [import ...] declarations
    | (sidecar: extract_and_rewrite_imports)
Import declarations + transformed source (imports replaced by __vcad_import_N symbols)
    | (driver: resolve each import via SketchUp Ruby bridge)
Resolved data (dimensions/bbox/transform JSON, or solid mesh/ADT)
    | (sidecar: inject into Loon environment + evaluate)
Result solid
```

## Dependency DAG and Cascade Updates

When VCAD nodes import from other entities, the driver maintains a dependency DAG to enable cascade updates.

### How it works

- Each `vcad_place` call registers the node and its import dependencies in the DAG
- DAG state is persisted to `.supex/vcad-state.json`
- `vcad_update` with `cascade=true` re-evaluates a node and all downstream dependents in topological order
- ADT composition: each node's result is cached in the sidecar, so downstream nodes importing `:solid` get the fresh ADT directly

### Cascade Example

```
base-plate.cmp.oo  →  bracket.cmp.oo (imports :solid from base-plate)
                   →  mount.cmp.oo (imports :dims from base-plate)
```

Calling `vcad_update("base-plate", cascade=true)` re-evaluates base-plate first, then bracket and mount in dependency order.

## File Watching

The sidecar watcher classifies changes in `.cmp.oo` source files and `.oo` library modules.

### Source file watching

- Auto-starts on first `vcad_place`
- Detects file modifications via the sidecar's filesystem watcher
- Provides change events consumed by driver-side update flows

### Module tracking

- When a `.cmp.oo` file uses `[use module-name]`, the sidecar tracks which `.oo` files are loaded
- Library change events can be used to re-evaluate all dependent nodes

### Batch editing

Use `vcad_watch_pause` / `vcad_watch_resume` to batch multiple file edits into a single cascade:

```
vcad_watch_pause()
# Edit multiple .cmp.oo files...
vcad_watch_resume()  # Flushes all accumulated changes as one cascade
```

## MCP Tool Surface (VCAD)

Canonical tool inventory and signatures live in [MCP Reference](agents/guide/mcp.md).

Practical VCAD tool flow:

1. `vcad_place(node_id, source_file, ...)` places or updates a node
2. `vcad_update(node_id, source_file?)` re-evaluates one node
3. `vcad_update(node_id, cascade=true)` re-evaluates downstream dependents in DAG order
4. `vcad_list_nodes()` verifies node IDs, source files, versions, and instance counts
5. `vcad_inspect(source)` returns `volume`, `surface_area`, `bbox`, and `is_empty` without placement
6. `vcad_watch_pause()` / `vcad_watch_resume()` batches multi-file edits into one cascade
7. `vcad_viewer_state`, `vcad_viewer_screenshot`, `vcad_viewer_focus` support viewer diagnostics
8. `vcad_health`, `vcad_metrics`, `vcad_reconcile_status` provide operational diagnostics

`vcad_export(source, format?, output_path?)` is available, but import-aware export paths can behave differently from direct sidecar export. Validate behavior in your target environment.

## Known Limitations

### Mesh CSG booleans (Phase 1)

Boolean operations (union, difference, intersection) between BRep and mesh-based solids are not fully supported. When one operand is BRep and the other is mesh (e.g. a native SketchUp solid imported via `:solid`), the kernel falls back to mesh concatenation instead of true CSG:

```rust
// vcad-kernel: boolean() for mixed BRep/Mesh cases
// "Phase 1 limitation — proper mesh CSG comes in Phase 2"
let mut combined = mesh_a;
combined.merge(&mesh_b);  // concatenation, not boolean
```

**Affected operations:**
- `[difference imported-mesh brep-solid]` — does not subtract, just merges meshes
- `[union imported-mesh brep-solid]` — merge behaves like union visually, but no intersection removal
- `[intersection imported-mesh brep-solid]` — returns merged mesh, not true intersection

**Workaround:** Use BRep primitives (cube, cylinder, sphere, cone) as boolean tools instead of imported meshes. BRep-on-BRep booleans work correctly.

**What works:** Native mesh imports are useful for visualization, positioning, and as base geometry. They participate correctly in transforms (translate, rotate, scale).

### Features on mesh solids

Fillet, chamfer, and shell operations only work on BRep solids. They return the solid unchanged for mesh-only solids.

### SketchUp manifold detection

The `Entities#manifold?` API is not available in all SketchUp versions. The runtime falls back to checking for the presence of faces (`entities.grep(Sketchup::Face).any?`) instead.

## Troubleshooting

For operational issues, use [Troubleshooting](agents/guide/troubleshooting.md#vcad-issues).

Most common VCAD failures:

- Sidecar startup/connectivity issues (`port 9877`, missing binary, crashed sidecar)
- Path/auth policy errors (`PATH_NOT_ALLOWED`, `AUTH_INVALID`)
- Import/update issues (`SOLID_IMPORT_UNAVAILABLE`, `ADT_CACHE_MISS`, stale geometry)
