# CLI Reference

The `./supex` command provides direct SketchUp interaction.

## Connection

| Command | Description |
|---------|-------------|
| `status` | Check SketchUp connection status |
| `reload` | Reload extension without restarting SketchUp |

## Ruby Execution

| Command | Description |
|---------|-------------|
| `eval <code>` | Execute Ruby code inline |
| `eval-file <path>` | Execute Ruby script from file (recommended) |

## Model Introspection

| Command | Description |
|---------|-------------|
| `info` | Display model statistics and state |
| `entities [type]` | List entities (all/faces/edges/groups/components) |
| `selection` | Show currently selected entities |
| `layers` | List all layers/tags |
| `materials` | List all materials |
| `camera` | Get camera position and settings |

## Visualization

| Command | Description |
|---------|-------------|
| `screenshot` | Capture view to PNG file |

## Model Management

| Command | Description |
|---------|-------------|
| `open <path>` | Open .skp file |
| `save [path]` | Save model (optionally to new path) |
| `export <format>` | Export to skp/obj/stl/png/jpg |

## Documentation

| Command | Description |
|---------|-------------|
| `docs tree` | Show documentation hierarchy |
| `docs show <uri>` | View specific documentation |
| `docs search <term>` | Search documentation |

For full options: `./supex --help` or `./supex <command> --help`
