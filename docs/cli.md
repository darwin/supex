# CLI Reference

The `./supex` command is the direct CLI interface for SketchUp automation.

For interactive Ruby console usage, see [Interactive REPL](repl.md).

## Commands

| Command | Description |
|---------|-------------|
| `./supex status` | Check SketchUp connectivity and local docs availability |
| `./supex reload` | Reload the SketchUp extension without restarting SketchUp |
| `./supex eval <code>` | Evaluate inline Ruby code |
| `./supex eval-file <path>` | Evaluate Ruby from a file (recommended workflow) |
| `./supex info` | Show current model stats |
| `./supex entities [type]` | List model entities (`all`, `faces`, `edges`, `groups`, `components`) |
| `./supex selection` | Show current selection |
| `./supex layers` | List layers/tags |
| `./supex materials` | List materials |
| `./supex camera` | Show active camera data |
| `./supex screenshot` | Save a screenshot to disk |
| `./supex open <path>` | Open `.skp` model |
| `./supex save [path]` | Save current model |
| `./supex export <format>` | Export current scene |

## Common Options

- `--host`, `-H`: Runtime host (default `localhost`)
- `--port`, `-p`: Runtime port (default `9876`)

`--raw`/`-r` JSON output is available on:
- `eval`
- `eval-file`
- `info`
- `entities`
- `selection`
- `layers`
- `materials`
- `camera`

## Export Formats

Runtime export currently supports:

- `skp`
- `obj`
- `stl`
- `png`
- `jpg`
- `jpeg`

## Examples

```bash
./supex status
./supex eval "Sketchup.version"
./supex eval-file /absolute/path/to/script.rb
./supex entities faces --raw
./supex screenshot --width 2560 --height 1440
./supex export obj
```
