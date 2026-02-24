# Radar

Single-host log aggregator for supex. Tails all subsystem logs, parses them into structured events, and displays them in a live TUI with filtering, search, and pluggable renderers.

```
┌─────────────────────────────────────────────────────────┐
│ FilterBar         source: mcp-*  level: WARN  pattern:  │
├────────┬──────────────┬───────┬──────────┬──────────────┤
│ EID    │ Time         │ Level │ Source   │ Message      │
│ a1b2c3 │ 12:34:56.789 │ WARN  │ mcp-pro… │ Timeout …   │
│ d4e5f6 │ 12:34:57.012 │ ERROR │ mcp-ste… │ Connection … │
├────────┴──────────────┴───────┴──────────┴──────────────┤
│ Detail: EID a1b2c3 │ Source: mcp-protocol │ Tab: raw    │
│ {"jsonrpc":"2.0","method":"tools/call","params":{…}}    │
├─────────────────────────────────────────────────────────┤
│ 142 events │ 2 shown │ 3 sources │ 4.2 ev/s │ browsing │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

Radar requires the `SUPEX_WORKSPACE` environment variable pointing to the project workspace root (where `.tmp/logs/` lives). Without it, radar refuses to start.

```bash
export SUPEX_WORKSPACE=/path/to/your/project
```

A convenient way to set this is via [direnv](https://direnv.net/) with an `.envrc` file in your workspace:

```bash
# .envrc
export SUPEX_WORKSPACE="$PWD"
```

The `mcp` wrapper sets `SUPEX_WORKSPACE` automatically for the MCP server process, but radar runs independently and needs the variable in its shell environment.

## Quick start

```bash
# Watch default supex log sources
./radar watch

# Ad-hoc files (ignores default sources)
./radar watch .tmp/logs/runtime-console.log .tmp/logs/mcp-protocol.jsonl

# Plain stdout (for piping or agent consumption)
./radar watch --plain

# With filters
./radar watch -l WARN -s mcp-protocol,cli-driver
```

The `radar` wrapper at the repo root resolves the supex project path and runs `uv run --project devtools/radar radar "$@"`.

## Commands

| Command | Description |
|---------|-------------|
| `radar watch` | Live log tailing with TUI or plain output |
| `radar parse <file>` | Parse and dump structured events from a file |
| `radar bench` | Benchmark buffer ingest, filter, and search throughput |

### `radar watch`

Three source modes (mutually exclusive):

1. **Default** — `radar watch` — tails all standard supex log files
2. **Ad-hoc** — `radar watch file1.log *.jsonl` — tails specified files/globs
3. **Config** — `radar watch -c radar.toml` — loads sources from TOML

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--config` | `-c` | — | TOML config with `[[source]]` entries |
| `--plain` | | false | Plain stdout stream, no TUI |
| `--level` | `-l` | — | Minimum level: DEBUG, INFO, WARN, ERROR, FATAL |
| `--source` | `-s` | — | Source filter (repeatable, comma-separated) |
| `--capacity` | | 10000 | Ring buffer size (min 100) |
| `--pane-name` | | `radar` | tmux pane title |
| `--no-mouse` | | false | Disable mouse events (useful over SSH) |

### `radar bench`

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--count` | `-n` | 100000 | Synthetic events to generate |
| `--capacity` | | 100000 | Ring buffer capacity |
| `--sources` | | 5 | Number of distinct sources |

## Default sources

When launched without arguments, radar tails these files relative to `$SUPEX_WORKSPACE` (or cwd):

| Source ID | File | Parser |
|-----------|------|--------|
| `mcp-protocol` | `.tmp/logs/mcp-protocol.jsonl` | jsonl |
| `mcp-stderr` | `.tmp/logs/mcp-stderr.log` | pipe |
| `cli-driver` | `.tmp/logs/cli-driver.log` | pipe |
| `cli-stdout` | `.tmp/logs/cli-stdout.log` | plain |
| `cli-stderr` | `.tmp/logs/cli-stderr.log` | pipe |
| `runtime-console` | `.tmp/logs/runtime-console.log` | pipe |
| `runtime-stdout` | `.tmp/logs/runtime-stdout.log` | plain |
| `runtime-stderr` | `.tmp/logs/runtime-stderr.log` | plain |
| `vcad-sidecar` | `.tmp/logs/vcad-sidecar-stderr.log` | pipe |
| `vcad-events` | `.tmp/logs/vcad-events.jsonl` | jsonl |

## TOML config

```toml
[[source]]
name = "my-app"
path = ".tmp/logs/my-app.log"
parser = "pipe"        # optional — auto-detected if omitted

[[source]]
name = "events"
path = ".tmp/logs/*.jsonl"   # glob patterns supported
parser = "jsonl"
```

When a glob expands to multiple files, source names get a `:stem` suffix (e.g. `events:mcp-protocol`).

## TUI keybindings

Keybindings avoid the tmux `Ctrl+b` prefix — all single-key.

| Key | Action |
|-----|--------|
| `q` | Quit |
| `f` | Toggle filter bar |
| `/` | Focus pattern input (opens filter bar) |
| `j` / `k` | Move cursor down / up (enters browse mode) |
| `g` / `G` | Jump to first / last event |
| `Enter` | Toggle detail panel |
| `Tab` | Switch detail view: summary ↔ raw |
| `Escape` | Return to streaming mode |

**Streaming mode** (default): auto-scrolls to newest events, no cursor.
**Browsing mode** (activated by `j`/`k`/`g`/`G`): cursor visible, no auto-scroll, detail panel follows selection.

## Architecture

```
FileTailer ──┐
FileTailer ──┤  MultiTailer ──→ Normalizer ──→ RingBuffer ──→ TUI / stdout
FileTailer ──┘                  (per source)   (ObservableBuffer)
```

### Pipeline

1. **Tailer** (`tailer.py`) — async file watchers with rotation/truncation detection, incomplete line buffering
2. **Parsers** (`parsers/`) — format-specific line parsing with auto-detection
3. **Normalizer** (`normalizer.py`) — multiline assembly, deterministic EID generation (SHA-256)
4. **Buffer** (`buffer.py`) — fixed-capacity deque with O(1) source tracking, filter, regex search
5. **Ingest** (`ingest.py`) — orchestrates tailer → normalizer → buffer, lazy parser selection

### Parsers

| Name | Format | Example |
|------|--------|---------|
| `pipe` | `timestamp\|LEVEL\|source\|message` | `2025-02-24T12:34:56.789\|INFO\|Runtime\|Model loaded` |
| `jsonl` | One JSON object per line | `{"timestamp":"...","level":"INFO","message":"..."}` |
| `plain` | Free text with optional timestamp/level extraction | `12:34:56 INFO Starting server...` |

Auto-detection samples the first lines: majority `{` → jsonl, majority `|` × 2+ → pipe, otherwise plain. The plain parser supports multiline continuation (Java stacktraces, Python tracebacks, indented lines).

### Renderers

Source-specific summary formatters registered in a pluggable registry:

| Source | Renderer | Format |
|--------|----------|--------|
| (default) | `DefaultSummaryRenderer` | `time level source message` |
| `mcp-protocol` | `MCPProtocolRenderer` | `time req/res method [tool]` |
| `runtime-console` | `ConsoleLogRenderer` | `time level message` |

**Hot-reload**: place a Python file with a `RENDERERS = {"source": renderer}` dict. The registry polls mtimes every second and reloads atomically on change, keeping the last known-good version on errors.

## Data model

```python
class Level(IntEnum):
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3
    FATAL = 4

@dataclass
class LogEvent:
    eid: str              # 6-char hex identifier
    timestamp: datetime
    level: Level
    source: str           # logical source ID
    source_path: str      # file path
    message: str
    structured: dict | None  # preserved JSON payload (jsonl)
    raw: str              # original text (multiline intact)
    multiline: bool

@dataclass
class FilterSpec:
    sources: list[str]          # empty = all
    min_level: Level
    pattern: re.Pattern | None  # message regex
    since: datetime | None
    until: datetime | None
```

## Development

```bash
# Run tests
uv run --project devtools/radar pytest devtools/radar/tests/

# Run specific test
uv run --project devtools/radar pytest devtools/radar/tests/test_parsers.py -v

# Performance benchmarks
./radar bench -n 100000
```

Requires Python ≥ 3.14. Dependencies managed by uv via `devtools/radar/pyproject.toml`.
