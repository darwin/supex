# VCAD Workflow Guide

Use this guide when the task is parametric CAD authoring in Loon.

## When To Choose VCAD

Use VCAD for:

- repeatable solids authored from source files (`.cmp.oo`)
- geometry built from reusable `.oo` modules
- dependency-aware updates between nodes

For mixed tasks, keep geometry in VCAD and do scene/model post-processing with Ruby.

## Workflow Loop

1. Author `.cmp.oo` node files and shared `.oo` modules.
2. Reuse existing CAD library modules before writing new geometry helpers.
3. Place nodes with `vcad_place` (imports are auto-detected and resolved).
4. Update with `vcad_update` (single node) or `vcad_update(..., cascade=true)` (dependent graph).
5. Verify with `vcad_list_nodes` and screenshots.

## Execution Rules

- `vcad_place(node_id, source_file, ...)` - place/update one node
- `vcad_update(node_id, source_file?, cascade?)` - re-evaluate one node; `cascade=true` includes downstream dependents in DAG order
- `vcad_watch_pause()` / `vcad_watch_resume()` - batch multi-file edits
- `vcad_eval(code)` - REPL-style Loon evaluation only (no placement)
- `vcad_inspect(source)` - inspect without placement

## Authoring Rules

### 1. One Solid Per Node

- Each `.cmp.oo` file must evaluate to exactly one solid
- Keep shared logic in `.oo` modules loaded via `[use ...]`
- Use multiple `.cmp.oo` files for multi-part assemblies

### 2. Reuse Existing CAD Library First

- Inspect existing project `.oo` modules first
- Prefer existing exported constructors/helpers
- Keep `.cmp.oo` files thin (parameter composition + library calls)

### 3. Import Semantics Are Strict

- `[import ...]` works in VCAD tools and `.cmp.oo` source
- `[import ...]` does not work in `.oo` modules loaded through `[use ...]`

### 4. Update and Dependency Safety

- Keep `node_id` stable for predictable updates and instance continuity
- Use cascade updates when downstream nodes depend on imports
- Pause/resume watch when editing multiple VCAD files

### 5. Supported Surface Only

- Use supported CAD constructors only
- Treat assembly/joint/simulation and ECAD forms as out of scope
- For mixed native-mesh + BRep booleans, verify carefully with screenshots and node inspection

### 6. Core Loon CAD Constructors

- Primitives: `cube`, `cylinder`, `sphere`, `cone`, `torus`, `wedge`, `prism` (n-gon by circumradius), `hex-prism` (across-flats), `polygon-prism`
- Booleans (subject-last): `union`, `difference`, `intersection`
- Transforms (subject-last): `translate`, `rotate`, `scale`
- Features (subject-last): `fillet`, `chamfer`, `shell`
- Patterns: `linear-pattern`, `circular-pattern`
- Sketch-based: `sketch`, `extrude`, `revolve`, `sweep-line`, `sweep-helix`, `loft`, `loft-closed`
- Scene/material: `root`, `material`
- Vendor geometry: `import-mesh` (STL) and `import-step`; relative paths resolve against the directory of the `.cmp.oo` file. STL is read in metres and scaled to millimetres, so for a millimetre file use `[import-mesh-scaled 0.001 0.001 0.001 "vendor/part.stl"]`. Mesh imports carry no BRep, so the native-mesh rules above apply

Authoritative constructor signatures: `cad-lib/src/lib.loon`.

Important: Loon has no runtime arithmetic operators (`+`, `-`, `*`, etc.). Use literals, `let`, and `fn` patterns.

## Functional Style

Loon geometries are immutable ADT trees. Every CAD operation returns a new tree — nothing is mutated in place. This makes composition safe and predictable: you build complex solids by threading a value through a sequence of pure transformations.

### `let` — Name and Reuse

Define constants and reusable tool shapes once with `let`, then reference them throughout the file:

```loon
[let t 4.0]                    ; material thickness
[let hole [cylinder 3.0 6.0]]  ; reusable bolt hole tool

[pipe [cube 60.0 40.0 t]
  [difference [translate 10.0 20.0 -1.0 hole]]
  [difference [translate 50.0 20.0 -1.0 hole]]]
```

This avoids duplicated literals and makes intent clear. When a dimension changes, update one `let` binding.

### `pipe` — Read Top to Bottom

All CAD functions take geometry as their **last** argument (subject-last design). `pipe` threads the result of each step as the last argument to the next:

```loon
[pipe [cylinder 15.0 20.0]
  [union [translate 0.0 0.0 -4.0 [cylinder 30.0 4.0]]]
  [difference [translate 0.0 0.0 -5.0 [cylinder 5.0 26.0]]]
  [difference [circular-pattern 0.0 0.0 0.0  0.0 0.0 1.0  6 360.0
    [translate 22.5 0.0 -5.0 [cylinder 3.0 10.0]]]]]
```

Reading top-to-bottom matches the order of operations: start with a cylinder, add a flange, bore the center, drill bolt holes.

### `fn` — Helpers for Repeated Operations

When the same operation appears multiple times (e.g. drilling holes at different positions), extract an `fn`. The function **must** take subject as its last parameter to work inside `pipe`:

```loon
[fn drill [x y tool s]
  [difference [translate x y -1.0 tool] s]]

[pipe [cube 120.0 80.0 5.0]
  [drill 60.0 40.0 [cylinder 15.0 7.0]]
  [drill 15.0 15.0 m5]
  [drill 105.0 15.0 m5]]
```

### Composition Pattern

A well-structured `.cmp.oo` file follows this order:

1. **`use`** — load shared modules
2. **`let`** — define constants and reusable tool shapes
3. **`fn`** — define helper functions (subject-last)
4. **`pipe`** — compose the final solid top-to-bottom

### Anti-patterns

- **Deeply nested calls instead of `pipe`:** Hard to read, easy to misplace brackets. Flatten with `pipe`.
- **Duplicated geometry instead of `let`/`fn`:** If the same shape or value appears twice, bind it.
- **Wrong argument order in `fn`:** Subject must be the last parameter, otherwise `pipe` threading breaks.

## Imports and Exports Notes

- Keep import declarations in `.cmp.oo` files.
- `[use name]` looks for `name.oo` beside the importing file first, then in each directory of `VCAD_LOON_PATH` (shared part libraries). Use dotted names for subdirectories (`[use hardware.screws]`); a local file shadows a lib module of the same name.
- Prefer stable entity references and stable `node_id` naming.
- `vcad_export(source, format?, output_path?)` is available; import-aware export behavior can differ from direct sidecar export, so validate in your environment.

## Examples

### Node with Shared Modules

```loon
; cmp/bracket.cmp.oo
[use shared/params :as p]
[use shared/lib :as lib]

[pipe [lib.base-bracket p.width p.depth p.height]
  [difference
    [translate p.hole_x p.hole_y 0.0
      [cylinder p.hole_radius p.height]]]
  [fillet p.edge_radius]]
```

### Import from Host Entity

```loon
[let host [import :host "entity:12345" :dims]]
[cube [get host :width] 10.0 [get host :height]]
```

`[import ...]` declarations must stay in `.cmp.oo` files (or inline code). They do not work in `.oo` modules loaded via `[use ...]`.

### Batch Editing Pattern

```text
vcad_watch_pause()
# edit multiple .cmp.oo and .oo files
vcad_watch_resume()  # flushes as one merged cascade update
```

## References

- Router and chooser: `README.md`
- Geometry QA: `ruby.md` § "Geometry Quality Rules"
- VCAD architecture/details: `docs/vcad.md` in the supex repository (not reachable through `supex-guide/`)
