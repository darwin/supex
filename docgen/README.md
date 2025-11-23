# SketchUp API Documentation Generator

Automated pipeline for generating AI-ready documentation from the SketchUp Ruby API stubs repository.

## Overview

This project generates Markdown documentation from the official SketchUp Ruby API stubs, optimized for use with Claude Code and other AI assistants. Instead of HTML documentation, it produces:

- **Markdown files** - One file per class/module, human and AI-readable
- **INDEX.md** - Concise overview for quick navigation (designed for Claude Code)

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
1. Clean previous output (`generated-sketchup-docs-md/`)
2. Parse SketchUp API with YARD
3. Generate clean Markdown documentation from YARD registry
4. Build `INDEX.md` for quick navigation

### Output Structure

```
generated-sketchup-docs-md/
├── INDEX.md              # Concise overview for Claude Code
├── Sketchup/
│   ├── Model.md
│   ├── Entity.md
│   ├── Curve.md
│   └── ...
├── Geom/
│   ├── Point3d.md
│   ├── Vector3d.md
│   └── ...
└── ...
```

## Filtering Documentation

The generator supports filtering to exclude irrelevant API namespaces and patterns. This is configured via `filter_config.yml`.

### Configuration File

Edit `filter_config.yml` to customize filtering:

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
```

### Default Filtering

By default, the following are excluded to focus on 3D modeling API:

- **Layout::*** - Layout API for 2D documentation and presentations
- **UI::*** - User interface components (dialogs, toolbars, menus)
- ***Observer** - All Observer classes (event handling system)
- **Sketchup::Extension*** - Extensions API (ExtensionsManager, Extension)
- **Sketchup::Licensing*** - Licensing API

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

## Using with Claude Code

The generated documentation is optimized for Claude Code workflow:

1. **Start with INDEX.md** - Claude reads this first to get an overview of available APIs
2. **Navigate to specific docs** - Based on the index, Claude loads only relevant MD files
3. **Efficient context usage** - Only load detailed documentation when needed

Example Claude Code prompt:
```
Read generated-sketchup-docs-md/INDEX.md to see available SketchUp APIs, then help me create a script that...
```

## Configuration

### .yardopts

YARD configuration file that specifies:
- Input paths (from `sketchup-api-stubs/` submodule)
- Plugins (yard-sketchup)
- Filters (no private APIs)

### Gemfile

Dependencies:
- `yard` - Documentation generation and parsing tool
- `yard-sketchup` - SketchUp-specific YARD handlers

## Architecture

```
┌─────────────────────────────────────────┐
│ sketchup-api-stubs (git submodule)      │
│ - Official SketchUp Ruby API stubs      │
│ - YARD comments + pages                 │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ YARD + yard-sketchup plugin             │
│ - Parse Ruby stubs                      │
│ - Build YARD registry (.yardoc)         │
└────────────────┬────────────────────────┘
                 │
          ┌──────┴──────┐
          ▼             ▼
┌──────────────────────┐  ┌─────────────────┐
│ generate_markdown_   │  │ build_index.rb  │
│ docs.rb              │  │                 │
│ - Read YARD registry │  │ - Create INDEX  │
│ - Generate clean MD  │  │                 │
└──────────────────────┘  └─────────────────┘
          │                      │
          └──────────┬───────────┘
                     ▼
┌──────────────────────────────────────────┐
│ generated-sketchup-docs-md/              │
│ - Clean Markdown files (no HTML)         │
│ - AI-ready documentation                 │
│ - Optimized for Claude Code              │
└──────────────────────────────────────────┘
```

## Development

### Scripts

- **generate_docs.sh** - Main generation pipeline orchestration
- **generate_markdown_docs.rb** - Generates clean Markdown from YARD registry
- **build_index.rb** - Creates INDEX.md from YARD registry

### Customization

To modify the Markdown output format, edit `scripts/generate_markdown_docs.rb`. The script uses `YARD::Registry` to access all parsed documentation data and generates clean Markdown without HTML artifacts.

To modify the index format, edit `scripts/build_index.rb`.

To change YARD parsing settings, edit `.yardopts`.

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
