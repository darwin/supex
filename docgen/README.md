# SketchUp API Documentation Generator

Automated pipeline for generating AI-ready Markdown documentation from the SketchUp Ruby API stubs repository.

## Overview

This project generates clean Markdown documentation from the official SketchUp Ruby API stubs, optimized for use with Claude Code and other AI assistants. The output includes:

- **Class/module documentation** - One Markdown file per class/module
- **TOP-LEVEL.md** - Global constants and methods
- **INDEX.md** - Concise API overview for quick navigation
- **Namespace indexes** - Per-namespace INDEX.md files with categorized listings
- **Tutorial pages** - Guide pages with URI-friendly hyphenated names

## Quick Start

```bash
cd docgen
git submodule update --init --recursive
bundle install
./scripts/generate_docs.sh
```

Output: `generated-sketchup-api-docs/`

## Requirements

- Ruby 2.7 or higher
- Bundler
- Git (for submodule management)

## Setup

### 1. Initialize the SketchUp API Stubs Submodule

```bash
cd docgen
git submodule add https://github.com/SketchUp/ruby-api-stubs.git sketchup-api-stubs
git submodule update --init --recursive
```

Or if the submodule is already configured:

```bash
git submodule update --init --recursive
```

### 2. Install Dependencies

```bash
bundle install
```

## Usage

### Generate Documentation

Run the generation script:

```bash
./scripts/generate_docs.sh
```

This will:
1. Clean previous output (`generated-sketchup-api-docs/`)
2. Validate that the submodule is initialized
3. Parse SketchUp API with YARD
4. Generate class/module documentation
5. Generate TOP-LEVEL.md for global constants and methods
6. Generate tutorial pages (with hyphenated filenames)
7. Build INDEX.md files (main + per-namespace)

## Output Structure

```
generated-sketchup-api-docs/
├── INDEX.md                  # Master API overview with navigation
├── TOP-LEVEL.md              # Global constants (ORIGIN, X_AXIS, etc.) and methods
├── Array.md                  # Ruby Array extensions for SketchUp
├── Length.md                 # Length class (unit handling)
├── Numeric.md                # Numeric extensions
├── String.md                 # String extensions
├── Geom.md                   # Geom module methods (fit_plane_to_points, etc.)
├── Sketchup.md               # Sketchup module methods (active_model, etc.)
├── Geom/
│   ├── INDEX.md              # Categorized: Points & Vectors, Transformations, etc.
│   ├── Point3d.md
│   ├── Vector3d.md
│   ├── Transformation.md
│   ├── BoundingBox.md
│   └── ...                   # ~12 geometry classes
├── Sketchup/
│   ├── INDEX.md              # Categorized: Model Structure, Geometry, etc.
│   ├── Model.md
│   ├── Entity.md
│   ├── Face.md
│   ├── Edge.md
│   └── ...                   # ~50 model classes
└── pages/
    ├── generating-geometry.md
    ├── importer-options.md
    └── exporter-options.md
```

## Configuration

### filter_config.yml

Main configuration file for filtering documentation content.

```yaml
# Top-level namespaces to exclude completely
excluded_namespaces:
  - Layout          # Layout API (2D documentation)
  - UI              # User interface components

# Patterns to exclude (glob-style wildcards)
excluded_patterns:
  - "*Observer"               # All Observer classes
  - "Sketchup::Extension*"    # Extensions API
  - "Sketchup::Licensing*"    # Licensing API

# Tutorial pages to include
included_pages:
  - generating_geometry
  - importer_options
  - exporter_options

# Constants to exclude from TOP-LEVEL.md
excluded_constant_patterns:
  - "CMD_*"         # Menu command constants
  - "VK_*"          # Virtual key constants
  - "MB_*"          # Mouse button constants
  - "GL_*"          # OpenGL constants
```

### .yardopts

YARD parser configuration:

```
--title "SketchUp Ruby API Documentation"
--output-dir tmp/yard-html
--no-api
--no-private
--hide-api Internal
--plugin yard-sketchup
--exclude sketchup-api-stubs/lib/sketchup-api-stubs/stubs/Layout
--exclude sketchup-api-stubs/lib/sketchup-api-stubs/stubs/UI
```

Key settings:
- `--plugin yard-sketchup` - Enables SketchUp-specific YARD handlers
- `--exclude` directives - First-stage filtering (before parsing)
- `--no-private` - Excludes private methods from documentation

## Filtering System

### Two-Stage Filtering

The generator uses two filtering stages for efficiency:

**Stage 1: YARD Parsing (.yardopts)**
- Excludes entire directories from parsing
- Applied before Ruby files are analyzed
- Configured via `--exclude` directives
- Example: Layout and UI namespaces excluded here

**Stage 2: Markdown Generation (filter_config.yml)**
- Fine-grained pattern matching on parsed objects
- Applied during documentation generation
- Supports glob-style wildcards
- Example: `*Observer` excludes all observer classes

This two-stage approach:
- Improves performance (less parsing)
- Provides flexibility (patterns vs directories)
- Allows different filtering for different use cases

### Default Filtering

By default, the following are excluded to focus on 3D modeling API:

- **Layout::** - Layout API for 2D documentation and presentations
- **UI::** - User interface components (dialogs, toolbars, menus)
- ***Observer** - All Observer classes (event handling system)
- **Sketchup::Extension*** - Extensions API (ExtensionsManager, Extension)
- **Sketchup::Licensing*** - Licensing API
- **Sketchup::Http*** - HTTP/Web API
- **Sketchup::Tool*** - Tool classes
- **Sketchup::View** - View manipulation
- **Sketchup::Shadow*** - Shadow settings

### Filtered vs Unfiltered

- **With filtering:** ~1,500-1,800 objects (core 3D modeling API)
- **Without filtering:** ~2,700 objects (complete API)

Filtered documentation is optimized for:
- Creating and manipulating 3D geometry
- Working with entities, faces, edges, groups, components
- Geometric operations (Geom:: namespace)
- Materials, layers, and model management

### Customizing Filters

To include more or less content:

1. Edit `filter_config.yml`
2. Add/remove namespaces or patterns
3. Regenerate: `./scripts/generate_docs.sh`

Example - include UI but exclude Layout:

```yaml
excluded_namespaces:
  - Layout    # Remove "UI" to include it

excluded_patterns:
  - "*Observer"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ sketchup-api-stubs (git submodule)                          │
│ Official SketchUp Ruby API stubs + tutorial pages           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ YARD + yard-sketchup plugin                                 │
│ Parse Ruby stubs → Build .yardoc registry                   │
│ [Stage 1 filtering via .yardopts --exclude]                 │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│ generate_sketchup_      │   │ build_sketchup_         │
│ api_docs.rb             │   │ api_index.rb            │
│                         │   │                         │
│ Outputs:                │   │ Outputs:                │
│ - Class/module *.md     │   │ - INDEX.md (master)     │
│ - TOP-LEVEL.md          │   │ - Geom/INDEX.md         │
│ - pages/*.md            │   │ - Sketchup/INDEX.md     │
│                         │   │                         │
│ [Stage 2 filtering]     │   │ [Stage 2 filtering]     │
└───────────┬─────────────┘   └───────────┬─────────────┘
            │                             │
            │    ┌────────────────┐       │
            └───►│ doc_helpers.rb │◄──────┘
                 │ (shared utils) │
                 └────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ generated-sketchup-api-docs/                                │
│ Clean Markdown documentation optimized for AI consumption   │
└─────────────────────────────────────────────────────────────┘
```

### Scripts

| Script | Purpose |
|--------|---------|
| `generate_docs.sh` | Pipeline orchestration |
| `generate_sketchup_api_docs.rb` | Class/module docs, TOP-LEVEL.md, pages |
| `build_sketchup_api_index.rb` | INDEX.md files (master + namespace) |
| `doc_helpers.rb` | Shared YARD text processing utilities |

**generate_docs.sh**

Main entry point. Orchestrates:
1. Clean previous output
2. Validate submodule
3. Run YARD parser
4. Generate documentation
5. Build indexes
6. Clean temporary files

**generate_sketchup_api_docs.rb**

Generates individual documentation files:
- One Markdown file per class/module
- TOP-LEVEL.md for global constants/methods
- Tutorial pages from submodule

**build_sketchup_api_index.rb**

Creates navigation indexes:
- Master INDEX.md with full API overview
- Per-namespace indexes with categorized listings

**doc_helpers.rb**

Shared utilities for YARD text processing (see Implementation Details).

## Implementation Details

### Text Processing (doc_helpers.rb)

Three core utilities for converting YARD documentation to clean Markdown:

**`convert_yard_references(text)`**

Converts YARD cross-reference syntax to Markdown code spans:
- `{ClassName}` -> `` `ClassName` ``
- `{#method}` -> `` `method` ``
- `{.class_method}` -> `` `class_method` ``
- `+code+` -> `` `code` ``

**`normalize_text(text)`**

Removes artificial line wrapping while preserving intentional formatting:
- Joins consecutive plain text lines
- Preserves paragraph breaks (blank lines)
- Preserves indented lines (code blocks)
- Preserves list items (`-`, `*`, `+`, numbered)

**`process_yard_text(text)`**

Combined pipeline: normalize_text + convert_yard_references

### Filtering Logic

Pattern matching converts glob wildcards to regex:
- `*Observer` -> `/^.*Observer$/`
- `Sketchup::Extension*` -> `/^Sketchup::Extension.*$/`

Constant filtering removes UI-related patterns from TOP-LEVEL.md:
- `CMD_*`, `VK_*`, `MB_*` (menu/keyboard constants)
- `GL_*` (OpenGL constants)
- Stub descriptions ("Stub value.") are filtered out

### Namespace Categorization

**Sketchup namespace (8 categories):**
- Model Structure: Model, DefinitionList, ComponentDefinition
- Geometry Primitives: Face, Edge, Curve, ArcCurve
- Containers: Group, ComponentInstance, Image
- Appearance: Material, Texture, RenderingOptions
- Organization: Layer, Layers, Pages, Page
- Annotations: Text, Dimension*
- Metadata: AttributeDictionary, AttributeDictionaries
- Camera & View: Camera, RenderingOptions

**Geom namespace (4 categories):**
- Points & Vectors: Point3d, Vector3d
- Transformations: Transformation
- Bounds & Meshes: BoundingBox, PolygonMesh
- Coordinates: LatLong, UTM

### Page Name Conversion

Tutorial pages are converted from underscore to hyphenated names:
- `generating_geometry.md` -> `generating-geometry.md`
- `importer_options.md` -> `importer-options.md`

This provides URI-friendly names consistent with web conventions.

## Using with Claude Code

The generated documentation is optimized for Claude Code workflow:

1. **Start with INDEX.md** - Claude reads this first to get an overview of available APIs
2. **Navigate to specific docs** - Based on the index, Claude loads only relevant MD files
3. **Efficient context usage** - Only load detailed documentation when needed

Example Claude Code prompt:
```
Read generated-sketchup-api-docs/INDEX.md to see available SketchUp APIs, then help me create a script that...
```

## Updating SketchUp API Version

To update to the latest SketchUp API version:

```bash
cd sketchup-api-stubs
git pull origin main
cd ..
./scripts/generate_docs.sh
```

To pin to a specific version:

```bash
cd sketchup-api-stubs
git checkout <tag-or-commit>
cd ..
./scripts/generate_docs.sh
```

## Troubleshooting

### Submodule not initialized

```
ERROR: sketchup-api-stubs submodule not found!
```

Solution:
```bash
git submodule update --init --recursive
```

### Missing gems

```
Could not find gem 'yard' or 'yard-sketchup'
```

Solution:
```bash
bundle install
```

### YARD parsing errors

Check that the submodule is properly initialized and contains valid Ruby files:
```bash
ls -la sketchup-api-stubs/lib/sketchup-api-stubs/stubs/
```

## License

This documentation generator is part of the Supex project. The SketchUp Ruby API stubs are maintained by SketchUp/Trimble.
