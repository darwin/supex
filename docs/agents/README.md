# Agents Documentation

This directory contains guidance for AI agents that model in SketchUp through Supex.

It covers both authoring workflows:

- Ruby workflow for direct SketchUp API automation
- VCAD workflow for parametric CAD in Loon (`.cmp.oo` + `.oo` modules)

## Canonical Sources

- `guide/README.md` - Router and workflow selection rules
- `guide/ruby.md` - Ruby workflow rules and patterns
- `guide/vcad.md` - VCAD workflow rules and constraints
- `guide/workflow.md` - Extended examples, visual QA, and practical snippets
- `guide/mcp.md` - Canonical MCP tool inventory (names and scope)

## Structure

```text
docs/agents/
├── README.md
└── guide/
    ├── README.md
    ├── ruby.md
    ├── vcad.md
    ├── workflow.md
    ├── api/      # SketchUp Ruby API docs (symlink)
    ├── stdlib/   # Ruby helper library docs (symlink)
    └── cad-lib/  # Loon CAD library source (symlink)
```

## Usage

In example projects, symlink `docs/agents/guide` as `supex-guide`:

```bash
ln -s /path/to/supex/docs/agents/guide supex-guide
```

Then reference `supex-guide/README.md` in your agent/project instructions.

## Maintenance

- Keep tool names and behavior aligned with `guide/mcp.md`
- Keep `guide/README.md` focused on rules; move long examples to `guide/workflow.md`
- Keep geometry pitfalls in `guide/ruby.md`; visual QA patterns in `guide/workflow.md`
- Do not edit generated API docs under `guide/api/`
