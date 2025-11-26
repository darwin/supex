# Supex Examples

Example projects are stored in **orphan branches** to keep them isolated from the main Supex repository. This ensures users working with examples don't inherit Supex-specific context.

## Available Examples

| Example | Branch | Description |
|---------|--------|-------------|
| simple-table | [`example-simple-table`](https://github.com/darwin/supex/tree/example-simple-table) | Basic workflow: creating a wooden table with modular Ruby scripts |

## Cloning an Example

Clone the example as a standalone project:

```bash
# Clone the simple-table example
git clone -b example-simple-table --single-branch git@github.com:darwin/supex.git simple-table

# Or using HTTPS:
git clone -b example-simple-table --single-branch https://github.com/darwin/supex.git simple-table

cd simple-table
```

## Browsing Online

You can browse example code directly on GitHub:

- [simple-table](https://github.com/darwin/supex/tree/example-simple-table)

## Creating New Examples

New examples follow the same pattern:

1. Create an orphan branch with prefix `example-`:
   ```bash
   git checkout --orphan example-my-project
   git rm -rf .
   # Add your example files
   git add .
   git commit -m "Initial commit: my-project example"
   git push -u origin example-my-project
   ```

2. Update this README with the new example entry.

## Running Examples

1. **Launch SketchUp with Supex:**
   ```bash
   cd /path/to/supex
   ./scripts/launch-sketchup.sh
   ```

2. **Open example in Claude Code:**
   ```bash
   cd simple-table
   # Ask Claude Code to help with the project
   ```

3. **Execute scripts:**
   - Claude Code can execute scripts using `eval_ruby_file`
   - Edit scripts in your IDE
   - Re-run after changes

4. **Verify results:**
   - `get_model_info()` - Check entity counts
   - `take_screenshot()` - Visual preview
   - `list_entities()` - Inspect geometry
