# vcad Integration

vcad is a BRep (Boundary Representation) kernel integrated into SketchUp via supex. The agent writes parametric CAD code in Loon (a Lisp with algebraic data types), the vcad Rust sidecar evaluates the code to produce BRep geometry, exports the mesh as OBJ, and SketchUp natively imports it as a component.

## Architecture

```
            AI Agent (Claude Code, MCP client)
                         |
                  [MCP Protocol (stdio)]
                         |
                supex Python MCP Driver
                /                    \
  [TCP JSON-RPC :9876]        [TCP JSON-RPC :9877]
         |                            |
  SketchUp Ruby Runtime       vcad Rust Sidecar
  (bridge_server.rb)          (loon-lang + vcad-eval + vcad-kernel)
         |                            |
  SketchUp Application         .vcad.loon files (source of truth)
```

### Evaluation Pipeline

```
.vcad.loon source
    | (loon-lang: parse + interpret)
Value::Adt tree (pure data)
    | (vcad-loon: value_to_document)
vcad_ir::Document (DAG of CsgOp nodes)
    | (vcad-eval: evaluate_document)
vcad_kernel::Solid (BRep geometry)
    | (Solid::to_mesh)
TriangleMesh
    | (OBJ export)
.obj file -> SketchUp definitions.import
```

### Components

| Component | Location | Language | Role |
|-----------|----------|----------|------|
| MCP Driver | `driver/src/supex_driver/` | Python | Exposes MCP tools, mediates sidecar and SketchUp |
| vcad Sidecar | `vcad/sidecar/` | Rust | Evaluates Loon code, produces BRep geometry + OBJ |
| Ruby Bridge | `runtime/src/supex_runtime/` | Ruby | Imports OBJ into SketchUp, manages vcad nodes |
| Viewer | `viewer/` | Rust/TypeScript | Standalone Tauri BRep preview |

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
   - Create a `.vcad.loon` file with a solid
   - Call `vcad_place("test-bracket", "bracket.vcad.loon")`
   - Verify the component appears: `vcad_list_nodes()`
   - Modify the source file
   - Call `vcad_update("test-bracket")`

## Writing .vcad.loon Files

Each `.vcad.loon` file must produce exactly one solid. The last expression is evaluated and converted to geometry.

### Data model

One `.vcad.loon` file = one SketchUp ComponentDefinition. For multi-part assemblies, use multiple files with shared modules:

```
project/
  src/
    build.loon           # Shared parametric functions
  base-plate.vcad.loon   # One solid output
  bracket.vcad.loon      # One solid output
```

### Example

```loon
; bracket.vcad.loon
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
[use build]                 ; Import module from build.loon
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
```

### Scene and Material

```loon
[root solid "material-name"]
[material "name" r g b metallic roughness]
```

## MCP Tools Reference

### vcad_place

Evaluate a `.vcad.loon` file and place the resulting mesh in SketchUp.

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | Unique identifier for this vcad node |
| `source_file` | string | Path to the `.vcad.loon` file |
| `position` | [x,y,z] | Position in mm (default [0,0,0]) |
| `component_name` | string | Optional SketchUp component name |

### vcad_update

Re-evaluate a vcad node and update SketchUp geometry. Atomic definition swap preserves instance placements.

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | The vcad node to update |
| `source_file` | string | Optional new source file (uses existing if omitted) |

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

List all vcad nodes in the current SketchUp model. No parameters.

Returns array of `{node_id, source_file, version, name, instances}`.

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

### OBJ import fails in SketchUp

- Verify the OBJ file exists and is not empty
- Check that SketchUp 2026 is running (uses `definitions.import` which returns ComponentDefinition directly)
- Review SketchUp console output for Ruby errors

### Stale geometry after update

The driver uses revision tracking to prevent stale results. If geometry appears outdated:
1. Check `vcad_list_nodes()` for version numbers
2. Call `vcad_update()` explicitly
3. Review `.supex/vcad-state.json` for revision gaps
