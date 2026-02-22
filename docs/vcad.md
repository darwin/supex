# VCAD Integration

VCAD is a BRep (Boundary Representation) kernel integrated into SketchUp via supex. The agent writes parametric CAD code in Loon (a Lisp with algebraic data types), the VCAD Rust sidecar evaluates the code to produce BRep geometry, exports the mesh as DAE, and SketchUp natively imports it as a component.

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
  SketchUp Application                       .skp.oo files (source of truth)
```

### Evaluation Pipeline

```
.skp.oo source
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
| VCAD Sidecar | `vcad/sidecar/` | Rust | Evaluates Loon code, produces BRep geometry + DAE |
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

### E2E test flow

1. Start sidecar: `./vcad-sidecar`
2. Start SketchUp with supex runtime: `./scripts/launch-sketchup.sh`
3. Via MCP tools:
   - Create a `.skp.oo` file with a solid
   - Call `vcad_place("test-bracket", "bracket.skp.oo")`
   - Verify the component appears: `vcad_list_nodes()`
   - Modify the source file
   - Call `vcad_update("test-bracket")`

## Writing .skp.oo Files

Each `.skp.oo` file must produce exactly one solid. The last expression is evaluated and converted to geometry.

### Data model

One `.skp.oo` file = one SketchUp ComponentDefinition. For multi-part assemblies, use multiple files with shared modules:

```
project/
  src/
    build.oo           # Shared parametric functions
  base-plate.skp.oo   # One solid output
  bracket.skp.oo      # One solid output
```

### Example

```loon
; bracket.skp.oo
[pipe [cube 50.0 30.0 5.0]
  [difference [cylinder 3.0 10.0]]
  [fillet 1.0]
  [translate 0.0 0.0 10.0]]
```

## Loon Language Quick Reference

Loon is a Lisp with algebraic data types, Hindley-Milner type inference, and square-bracket syntax.

### Basics

```loon
; Comments start with semicolon
[let x 42]                  ; Variable binding
[fn add [a b] [+ a b]]     ; Function definition
[pub fn square [x] [* x x]] ; Public function (exported)
[if condition then-expr else-expr] ; Conditional
```

### Pipe operator

Thread-last macro for chaining:

```loon
[pipe [cube 10.0 10.0 10.0]
  [fillet 2.0]
  [translate 0.0 0.0 5.0]]
; Equivalent to:
; [translate 0.0 0.0 5.0 [fillet 2.0 [cube 10.0 10.0 10.0]]]
```

### Module system

```loon
[use build]                 ; Import module from build.oo
[build.make-plate]          ; Call exported function
```

### Algebraic Data Types

All geometry constructors produce ADT values (pure data, no BRep objects):

```loon
[cube 10.0 10.0 10.0]      ; -> Cube 10.0 10.0 10.0
[fillet 2.0 solid]          ; -> Fillet solid 2.0
```

## Loon CAD API Reference

### Primitives

| Constructor | Signature | ADT |
|------------|-----------|-----|
| `cube` | `[cube x y z]` | `Cube f64 f64 f64` |
| `cylinder` | `[cylinder r h]` | `Cylinder f64 f64` |
| `sphere` | `[sphere r]` | `Sphere f64` |
| `cone` | `[cone rb rt h]` | `Cone f64 f64 f64` |

### Booleans (subject-last)

| Constructor | Signature | Description |
|------------|-----------|-------------|
| `union` | `[union other s]` | Add solids together |
| `difference` | `[difference tool s]` | Subtract tool from subject |
| `intersection` | `[intersection other s]` | Keep common volume |

### Transforms (subject-last)

| Constructor | Signature | Description |
|------------|-----------|-------------|
| `translate` | `[translate x y z s]` | Move in mm |
| `rotate` | `[rotate x y z s]` | Rotate in degrees |
| `scale` | `[scale x y z s]` | Scale factors |

### Features (subject-last)

| Constructor | Signature | Description |
|------------|-----------|-------------|
| `fillet` | `[fillet r s]` | Round edges |
| `chamfer` | `[chamfer d s]` | Bevel edges |
| `shell` | `[shell t s]` | Hollow solid |

### Patterns (subject-last)

| Constructor | Signature |
|------------|-----------|
| `linear-pattern` | `[linear-pattern dx dy dz count spacing s]` |
| `circular-pattern` | `[circular-pattern ox oy oz ax ay az count angle s]` |

### Sketch and Extrude

```loon
[sketch ox oy oz xx xy xz yx yy yz segments]
[extrude dx dy dz sk]
[revolve aox aoy aoz adx ady adz angle sk]
```

### Sweep and Loft

```loon
[sweep-line sx sy sz ex ey ez sk]
[sweep-helix radius pitch height turns sk]
[loft sketches]
[loot-closed sketches]
```

### Scene and Material

```loon
[root solid "material-name"]
[material "name" r g b metallic roughness]
```

### Assembly (out of scope)

The upstream VCAD cad-lib defines assembly, joint, and simulation types. These are not supported by the supex sidecar.

```loon
; Parts and instances
[part "name" solid "material"]
[instance "name" "part-name" x y z]

; Joints
[revolute-joint "name" ax ay az lo hi "parent" px py pz "child" cx cy cz]
[prismatic-joint "name" ax ay az lo hi "parent" px py pz "child" cx cy cz]
[fixed-joint "name" "parent" px py pz "child" cx cy cz]
[ball-joint "name" "parent" px py pz "child" cx cy cz]

; Assembly
[assembly parts instances joints "ground-part"]
```

### ECAD (out of scope)

Electronic CAD types for schematic and PCB design. Not supported by the supex sidecar.

```loon
[ecad-component "ref" "value" "footprint-id" x y rotation]
[ecad-wire x1 y1 x2 y2]
[ecad-trace x1 y1 x2 y2 width "layer" "net"]
[ecad-via x y diameter drill "net"]
[ecad-footprint "ref" "value" "footprint" x y rotation front]
```

## Import System

VCAD nodes can reference data from existing SketchUp entities using inline `[import ...]` declarations. The driver resolves these references before evaluation.

### Import syntax

```loon
[let <binding> [import <extract-type> "entity:<id>"]]
```

### Data imports

Extract numeric data from SketchUp entities and bind to Loon variables:

| Extract | Binding type | Fields |
|---------|-------------|--------|
| `:dimensions` | map | `:width`, `:height`, `:depth` (mm) |
| `:bbox` | map | `:min [x,y,z]`, `:max [x,y,z]` (mm) |
| `:transform` | map | `:matrix` (16-element array) |

```loon
; Parametric part that adapts to a host entity
[let host [import :dimensions "entity:12345"]]
[cube [get host :width] 10.0 [get host :height]]
```

### Solid imports

Import a solid for CSG composition. Works with both VCAD-backed nodes and native SketchUp solids.

```loon
; Import another VCAD node's geometry for boolean operations
[let bracket [import :solid "entity:67890"]]
[pipe [cube 100.0 50.0 20.0]
  [difference bracket]]
```

**VCAD-backed entities**: The cached ADT tree is injected directly from the sidecar's ADT cache. The source node must be evaluated first.

**Native SketchUp solids**: Groups and ComponentInstances with face geometry are triangulated in SketchUp and forwarded to the sidecar as `ImportedMesh` ADT values. Requires `vcad_place_with_imports` (not plain `vcad_place`).

### Import resolution flow

```
.skp.oo source with [import ...] declarations
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

- Each `vcad_place_with_imports` call registers the node and its import dependencies in the DAG
- DAG state is persisted to `.supex/vcad-state.json`
- `vcad_update_cascade` re-evaluates a node and all downstream dependents in topological order
- ADT composition: each node's result is cached in the sidecar, so downstream nodes importing `:solid` get the fresh ADT directly

### Example

```
base-plate.skp.oo  →  bracket.skp.oo (imports :solid from base-plate)
                   →  mount.skp.oo (imports :dimensions from base-plate)
```

Calling `vcad_update_cascade("base-plate")` re-evaluates base-plate first, then bracket and mount in dependency order.

## File Watching

The driver watches `.skp.oo` source files and `.loon` library modules for changes.

### Source file watching

- Auto-starts on first `vcad_place` or `vcad_place_with_imports`
- Detects file modifications via the sidecar's filesystem watcher
- Triggers re-evaluation of affected nodes

### Module tracking

- When a `.skp.oo` file uses `[use module-name]`, the sidecar tracks which `.loon` files are loaded
- Changes to library modules trigger re-evaluation of all nodes that depend on them

### Batch editing

Use `vcad_watch_pause` / `vcad_watch_resume` to batch multiple file edits into a single cascade:

```
vcad_watch_pause()
# Edit multiple .skp.oo files...
vcad_watch_resume()  # Flushes all accumulated changes as one cascade
```

## MCP Tools Reference

### vcad_place

Evaluate a `.skp.oo` file and place the resulting mesh in SketchUp.

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | Unique identifier for this VCAD node |
| `source_file` | string | Path to the `.skp.oo` file |
| `position` | [x,y,z] | Position in mm (default [0,0,0]) |
| `component_name` | string | Optional SketchUp component name |

### vcad_place_with_imports

Place a VCAD node that references SketchUp entities via `[import ...]` declarations. The driver resolves imports (data extracts, solid ADTs, native meshes) before evaluation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | Unique identifier for this VCAD node |
| `source_file` | string | Path to the `.skp.oo` file |
| `position` | [x,y,z] | Position in mm (default [0,0,0]) |
| `component_name` | string | Optional SketchUp component name |

### vcad_update

Re-evaluate a VCAD node and update SketchUp geometry. Atomic definition swap preserves instance placements.

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | The VCAD node to update |
| `source_file` | string | Optional new source file (uses existing if omitted) |

### vcad_update_cascade

Re-evaluate a node and all downstream dependents in topological order. The driver walks the dependency DAG and updates each node sequentially.

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | The root VCAD node to re-evaluate |

Returns `{success, updated: [node_ids], failed: [node_ids], results: [...]}`.

### vcad_inspect

Inspect geometry properties without placing in SketchUp.

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | string | File path or inline Loon code |

Returns: volume, surface_area, bounding_box.

### vcad_export

Export geometry to OBJ or STEP format.

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | string | File path or inline Loon code |
| `format` | string | "obj" or "step" (default "obj") |
| `output_path` | string | Optional output path |

### vcad_eval

REPL mode evaluation of Loon code. Returns display string, no geometry output.

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | string | Loon source code |

### vcad_list_nodes

List all VCAD nodes in the current SketchUp model. No parameters.

Returns array of `{node_id, source_file, version, name, instances}`.

### vcad_watch_pause

Pause reactive file watching. File changes accumulate but don't trigger re-evaluation. Use before editing multiple `.skp.oo` files in sequence. No parameters.

### vcad_watch_resume

Resume file watching and flush all accumulated changes. Merges, deduplicates, and topologically sorts pending changes, then executes as a single cascade. No parameters.

### vcad_viewer_state

Get current VCAD viewer state: camera position, selection, visible nodes. No parameters.

### vcad_viewer_screenshot

Capture screenshot from the VCAD viewer. Returns metadata with workspace-relative file path. The PNG is saved to `.tmp/vcad-viewer/`. No parameters.

### vcad_viewer_focus

Focus viewer camera on a specific VCAD node.

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | The VCAD node identifier to focus on |

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

### Sidecar not starting

Check the binary exists:
```bash
ls vcad/sidecar/target/release/supex-vcad-sidecar
```
If missing, build it:
```bash
cargo build --release --manifest-path vcad/sidecar/Cargo.toml
```

### Connection refused on port 9877

The sidecar is not running. Start it:
```bash
./vcad-sidecar
```
Or check if it crashed -- review logs:
```bash
cat .tmp/logs/vcad-sidecar-stderr.log
```

### PATH_NOT_ALLOWED errors

The sidecar enforces workspace path containment. Ensure:
- `SUPEX_WORKSPACE` is set to your project root
- Source files are inside the workspace
- No `..` path components in file references

### AUTH_INVALID errors

Token mismatch between driver and sidecar. Ensure `VCAD_AUTH_TOKEN` is set consistently in both environments.

### Non-loopback bind fails on startup

The sidecar requires both `VCAD_ALLOW_REMOTE=1` and `VCAD_AUTH_TOKEN` to bind to non-loopback addresses. This is a security measure to prevent unauthenticated remote access.

### DAE import fails in SketchUp

- Verify the DAE file exists and is not empty
- Check that SketchUp 2026 is running (uses `definitions.import` which returns ComponentDefinition directly)
- Review SketchUp console output for Ruby errors

### Stale geometry after update

The driver uses revision tracking to prevent stale results. If geometry appears outdated:
1. Check `vcad_list_nodes()` for version numbers
2. Call `vcad_update()` explicitly
3. Review `.supex/vcad-state.json` for revision gaps

### SOLID_IMPORT_UNAVAILABLE

The `:solid` import requires either:
- A VCAD-backed entity (has `vcad_node_id` attribute) — ADT retrieved from sidecar cache
- A native SketchUp solid with face geometry — mesh triangulated and forwarded as `ImportedMesh`

If neither condition is met, the import fails. Verify the target entity is a Group or ComponentInstance with geometry.

### ADT_CACHE_MISS

When importing `:solid` from a VCAD-backed entity, the source node must be evaluated before it can be imported. Call `vcad_update` on the source node first, or use `vcad_update_cascade` to ensure correct evaluation order.
