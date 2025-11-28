# Supex Examples

Example projects demonstrating SketchUp automation with Supex MCP.

## Overview

Examples are stored in **orphan branches** prefixed with `example-` to keep them isolated from the main Supex repository. This ensures users working with examples don't inherit Supex-specific context and can work with standalone projects.

## Available Examples

| Example | Branch | Description |
|---------|--------|-------------|
| simple-table | [`example-simple-table`](https://github.com/darwin/supex/tree/example-simple-table) | Complete tutorial: wooden table with modular Ruby scripts, demonstrates workflow, idempotence, and geometry patterns |

## Prerequisites

Before working with examples, ensure you have:

- **SketchUp 2026** (or later) installed
- **Supex runtime** installed in SketchUp (see main [README](../README.md))
- **Claude Code** or another MCP client
- **Ruby 3.2.2** (via mise, rbenv, or similar) for local development

## Quick Start

### 1. Clone an Example

```bash
# Clone the simple-table example
git clone -b example-simple-table --single-branch git@github.com:darwin/supex.git simple-table

# Or using HTTPS:
git clone -b example-simple-table --single-branch https://github.com/darwin/supex.git simple-table

cd simple-table
```

### 2. Configure MCP Server

Create `.mcp.json` in your project root pointing to your Supex installation:

```json
{
  "mcpServers": {
    "supex": {
      "command": "/path/to/supex/mcp"
    }
  }
}
```

### 3. Launch SketchUp

```bash
cd /path/to/supex
./scripts/launch-sketchup.sh
```

### 4. Open in Claude Code

```bash
cd simple-table
claude   # Or open in your MCP client
```

### 5. Execute Scripts

Ask Claude Code to run scripts:
- "Run src/create_table.rb"
- Claude uses `eval_ruby_file()` to execute

### 6. Verify Results

Use introspection tools:
- `get_model_info()` - Check entity counts
- `take_screenshot()` - Visual preview
- `list_entities()` - Inspect geometry

## Browsing Online

View example code directly on GitHub:
- [simple-table](https://github.com/darwin/supex/tree/example-simple-table) - Complete tutorial with step-by-step instructions

## Setting Up Your Own Project

### Project Structure

```
my-project/
├── .mcp.json           # MCP server configuration (not committed)
├── CLAUDE.md           # AI guidance for your project
├── README.md           # Project documentation
├── Gemfile             # Ruby dependencies
├── .rubocop.yml        # Code style (optional)
└── src/                # Ruby scripts
    ├── helpers.rb      # Reusable utilities
    └── main.rb         # Entry point
```

### Creating CLAUDE.md

Option 1: **Copy the template**
```bash
cp /path/to/supex/examples/USER-CLAUDE.md ./CLAUDE.md
# Customize for your project
```

Option 2: **Include via Claude Code context**
```markdown
# In your CLAUDE.md:
@/path/to/supex/examples/USER-CLAUDE.md

## Project-Specific Instructions
<!-- Add your custom instructions here -->
```

This keeps your project in sync with Supex documentation updates.

### MCP Configuration

The `.mcp.json` file should point to your Supex installation:

```json
{
  "mcpServers": {
    "supex": {
      "command": "/path/to/supex/mcp"
    }
  }
}
```

Add `.mcp.json` to `.gitignore` since paths vary per developer.

## Creating New Examples

To contribute a new example:

1. **Create an orphan branch** with `example-` prefix:
   ```bash
   git checkout --orphan example-my-project
   git rm -rf .
   ```

2. **Add your example files** following the project structure above

3. **Write comprehensive documentation**:
   - README.md with step-by-step tutorial
   - CLAUDE.md for AI guidance
   - Inline comments in Ruby code

4. **Commit and push**:
   ```bash
   git add .
   git commit -m "Initial commit: my-project example"
   git push -u origin example-my-project
   ```

5. **Update this README** by adding your example to the table above

### Example Best Practices

- **Idempotence**: Scripts should be safe to re-run multiple times
- **Modularity**: Separate concerns into multiple files
- **Documentation**: Use YARD comments on all public functions
- **Error handling**: Always use start_operation/commit_operation with rescue
- **Naming**: Use descriptive names for groups and components
- **Metrics**: Use metric units (meters, centimeters)

## Troubleshooting

### Connection Issues

**"SketchUp not connected"**
- Ensure SketchUp is running with Supex runtime
- Check that the runtime is loaded (Ruby Console should show startup message)
- Verify `.mcp.json` path is correct

### Script Errors

**"No such file"**
- Use absolute paths or paths relative to project root
- Check that the file exists and has `.rb` extension

**Ruby syntax errors**
- Run RuboCop locally: `bundle exec rubocop src/`
- Check Ruby Console in SketchUp for detailed errors

### Geometry Issues

**Faces created inside-out**
- Check face normal direction before pushpull
- Use `face.reverse!` if normal points wrong direction

**Duplicate geometry**
- Implement idempotence pattern with cleanup_by_name_and_attribute
- Check that start_operation uses unique names

## Resources

- [Supex Documentation](../README.md) - Main project documentation
- [Driver README](../driver/README.md) - MCP tools and CLI reference
- [SketchUp Ruby API](https://ruby.sketchup.com/) - Official API documentation
