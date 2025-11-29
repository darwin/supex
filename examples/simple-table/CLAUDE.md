# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an example project demonstrating the project-based workflow for Supex (SketchUp Model Context Protocol). It shows how to create 3D models in SketchUp using Ruby scripts stored in your project directory.

## Prerequisites

This example requires:
- SketchUp running with Supex extension loaded
- Supex server configured in Claude Code
- Parent repository setup at `/path/to/supex`

To launch SketchUp with the extension:
```bash
cd /path/to/supex
./scripts/launch-sketchup.sh
```

## Working with Scripts

### Executing Scripts

Run Ruby scripts in SketchUp using the `eval_ruby_file` tool:
- `scripts/create_table.rb` - Creates a basic wooden table with four legs
- `scripts/add_decorations.rb` - Adds decorative trim (requires table to exist)

### Verifying Results

After running scripts, use introspection tools:
- `get_model_info()` - Check entity counts and model state
- `take_screenshot()` - Get visual preview of the model
  - **Save to `_tmp/` directory with descriptive name** (e.g., `_tmp/table-initial.png`)
  - Tool returns file path only (saves ~21k tokens vs returning image data)
  - Only use Read tool on screenshot if user explicitly asks to see it
- `list_entities('groups')` - Inspect created groups and components
- `get_selection()` - Verify what's selected

### Saving Work

Use `save_model("model.skp")` to save the model to the project directory.

## Script Architecture

Scripts follow SketchUp best practices:
- Always use `model.start_operation()` / `model.commit_operation()` for undo/redo support
- Organize geometry in named groups for better structure
- Use metric units (e.g., `1.2.m`)
- Wrap operations in begin/rescue blocks with `model.abort_operation` on error
- Add materials for visual appearance

## Modifying the Example

When editing scripts:
1. Edit the Ruby file in your IDE (full syntax highlighting available)
2. Re-run the script using `eval_ruby_file`
3. Use introspection tools to verify changes
4. Iterate as needed

Scripts are version controlled with git, making it easy to track changes and collaborate.
