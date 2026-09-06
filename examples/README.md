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
- **Ruby 3.2.2** (via rbenv or similar; see `.ruby-version`) for local development

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

Register the Supex MCP server in the project scope. This writes `.mcp.json` into the project root:

```bash
claude mcp add --scope project --transport stdio supex \
  -e SUPEX_WORKSPACE="$(pwd)" \
  -- /path/to/supex/mcp
```

`SUPEX_WORKSPACE` is the project directory: relative paths in file tools resolve against it and logs and
screenshots land in its `.tmp/`. If the variable is omitted, the `mcp` wrapper falls back to the directory
the agent started the server in. See [MCP Configuration](#mcp-configuration) for the resulting file.

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

### Linking Supex Documentation

Create a symlink to Supex agent documentation:

```bash
# In your project root:
ln -s /path/to/supex/docs/agents/guide supex-guide
```

This gives your AI agents access to:
- `supex-guide/README.md` - Main agent prompt and conventions
- `supex-guide/ruby.md` - Ruby workflow rules, geometry lessons and pitfalls
- `supex-guide/vcad.md` - VCAD workflow rules and constraints
- `supex-guide/workflow.md` - Extended examples and visual QA
- `supex-guide/mcp.md` - MCP tool inventory
- `supex-guide/troubleshooting.md` - Common issues and solutions
- `supex-guide/api/` - SketchUp API documentation
- `supex-guide/stdlib/` - Ruby helper library (SupexStdlib) reference
- `supex-guide/cad-lib/` - Loon CAD library source and constructor signatures

### Creating CLAUDE.md

Include the symlinked documentation in your CLAUDE.md:

```markdown
# In your CLAUDE.md:
@supex-guide/README.md

## Project-Specific Instructions
<!-- Add your custom instructions here -->
```

This keeps your project in sync with Supex documentation updates.

Add `supex-guide` to your `.gitignore` since the symlink path varies per developer.

### Claude Code Permissions

By default Claude Code asks before every Supex tool call. To let the agent model without prompts, allow the
Supex tools in `.claude/settings.json` (shared with the project) or `.claude/settings.local.json` (per developer):

```json
{
  "permissions": {
    "allow": ["mcp__supex__*"]
  }
}
```

The runtime path policy still limits file operations to the workspace, so allowing the tools does not open
the whole filesystem. For guidance that should apply only to some files, Claude Code also reads
`.claude/rules/*.md`; a rule with a `paths:` frontmatter (for example `paths: ["**/*.oo"]`) loads only when
the agent works on matching files, which keeps VCAD conventions out of the way of Ruby scripts.

### MCP Configuration

`claude mcp add --scope project` (see above) produces a `.mcp.json` equivalent to:

```json
{
  "mcpServers": {
    "supex": {
      "type": "stdio",
      "command": "/path/to/supex/mcp",
      "env": { "SUPEX_WORKSPACE": "/path/to/my-project" }
    }
  }
}
```

Other MCP clients take the same command and environment variable (for example `gemini mcp add` or
`codex mcp add`). Add `.mcp.json` to `.gitignore` since paths vary per developer.

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

## Troubleshooting

### Connection Issues

**"SketchUp not connected"**
- Ensure SketchUp is running with Supex runtime
- Check that the runtime is loaded (Ruby Console should show startup message)
- Verify `.mcp.json` path is correct

### Script Errors

**"No such file"**
- Use absolute paths or paths relative to the project root (the workspace)
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
