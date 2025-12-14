# CLI Reference

The `./supex` command provides direct SketchUp interaction.

## Interactive Development

| Command | Description |
|---------|-------------|
| `./repl` | Start interactive Ruby REPL connected to SketchUp |

The REPL provides a terminal-based interface for executing Ruby code directly in SketchUp's context. See [Interactive REPL](repl.md) for full documentation.

```bash
./repl              # Connect with defaults
./repl --pry        # Use Pry mode for IDE integration
./repl -p 5000      # Connect to custom port
```

## Connection

| Command | Description |
|---------|-------------|
| `./supex status` | Check SketchUp connection status |
| `./supex reload` | Reload extension without restarting SketchUp |

## Ruby Execution

| Command | Description |
|---------|-------------|
| `./supex eval <code>` | Execute Ruby code inline |
| `./supex eval-file <path>` | Execute Ruby script from file (recommended) |

## Model Introspection

| Command | Description |
|---------|-------------|
| `./supex info` | Display model statistics and state |
| `./supex entities [type]` | List entities (all/faces/edges/groups/components) |
| `./supex selection` | Show currently selected entities |
| `./supex layers` | List all layers/tags |
| `./supex materials` | List all materials |
| `./supex camera` | Get camera position and settings |

## Visualization

| Command | Description |
|---------|-------------|
| `./supex screenshot` | Capture view to PNG file |

## Model Management

| Command | Description |
|---------|-------------|
| `./supex open <path>` | Open .skp file |
| `./supex save [path]` | Save model (optionally to new path) |
| `./supex export <format>` | Export to skp/obj/stl/png/jpg |

For full options: `./supex --help` or `./supex <command> --help`
