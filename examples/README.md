# Supex Examples

This directory contains example projects demonstrating the project-based workflow for Supex.

## Available Examples

### [simple-table](./simple-table/)
Demonstrates the basic workflow of creating a wooden table with:
- Project structure with scripts directory
- Modular Ruby scripts for different features
- Use of introspection tools
- Git-trackable code

## Running Examples

1. **Launch SketchUp with Supex:**
   ```bash
   cd /path/to/supex
   ./scripts/launch-sketchup.sh
   ```

2. **Open example in Claude Code:**
   ```bash
   cd examples/simple-table
   # Ask Claude Code to help with the project
   ```

3. **Execute scripts:**
   - Claude Code can execute scripts using `eval_ruby_file`
   - You can edit scripts in your IDE
   - Re-run scripts after making changes

4. **Verify results:**
   - Use `get_model_info()` to check model statistics
   - Use `take_screenshot()` for visual preview
   - Use `list_entities()` to inspect geometry

## Creating Your Own Projects

Use these examples as templates for your own SketchUp projects:

1. Create project directory with `scripts/` subdirectory
2. Write Ruby scripts following SketchUp best practices
3. Execute with `eval_ruby_file`
4. Use introspection tools to verify
5. Commit to git for version control

## Key Workflow Benefits

- **Git Integration**: All scripts are version controllable
- **IDE Support**: Full syntax highlighting and linting
- **Iterative Development**: Edit and re-run easily
- **Team Collaboration**: Share scripts with team members
- **Documentation**: Scripts serve as documentation
