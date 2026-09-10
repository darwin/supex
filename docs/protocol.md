# Communication Protocol

Supex uses newline-delimited JSON-RPC 2.0 over local sockets.

## Transports and Ports

| Port | Transport | Channel | Purpose |
|------|-----------|---------|---------|
| `9876` | TCP | Driver/CLI <-> SketchUp runtime | Bridge tools (`tools/call`) |
| `4433` | TCP | REPL client <-> REPL server | Interactive Ruby `eval` |
| `9877` | TCP | Driver <-> VCAD sidecar | VCAD evaluation/import tooling |
| `9878` | WebSocket | Driver <-> VCAD viewer | Viewer relay/state/screenshot |

## Message Framing

- JSON-RPC 2.0 envelope
- UTF-8 encoded JSON
- One message per line (`\n`-delimited)

## Bridge Runtime (`:9876`)

### Hello Handshake

Clients identify first using `hello`.

```json
{
  "jsonrpc": "2.0",
  "method": "hello",
  "params": {
    "name": "supex-driver",
    "version": "X.Y.Z",
    "agent": "mcp",
    "pid": 12345,
    "token": "optional",
    "workspace": "/abs/workspace/path"
  },
  "id": "hello"
}
```

Required params: `name`, `version`, `agent`, `pid`. `version` is the client's own version (the driver sends its package version); `X.Y.Z` above is a placeholder.

### Methods

- `hello`
- `ping`
- `resources/list`
- `tools/call`

The legacy command format (top-level `command` and `parameters` instead of `method: "tools/call"`), deprecated in 0.3.0, is no longer accepted: such requests get a `-32601` "Method not found" error.

`tools/call` payload:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "eval_ruby",
    "arguments": {"code": "Sketchup.version"}
  },
  "id": 2
}
```

### Connection Lifecycle

The driver exposes a logically persistent connection and auto-reconnects on failure/idle timeout. The runtime may close a socket after non-`hello` request handling, so reconnect behavior is expected.

### Retry and Replay

The runtime executes a `tools/call` as soon as the complete request line arrives, on the SketchUp main thread, and cannot be interrupted by the client. The driver therefore distinguishes two failure classes:

- Failure before the request bytes were sent (connect, `hello`, broken pipe on send): retried up to `SUPEX_RETRIES` times with a fresh connection.
- Timeout or dropped connection after the request was sent: the outcome is unknown. The request is sent again only for read-only tools (`ping`, `get_*`, `list_entities`, `get_selection`, `list_vcad_nodes`, `get_vcad_node`, `vcad.observer_poll`, `console_capture_status`, `resources/list`). For every other tool the driver raises `SketchUpUnknownResultError` (MCP result `error_type: "unknown_result"`) and the caller inspects the model before repeating the request.

Request IDs are not deduplicated by the runtime; two requests with the same `id` run twice.

### Expected Model Guard

Any `tools/call` may carry `expected_model_path` in `arguments`. Before dispatching the tool, the runtime compares it with the path of `Sketchup.active_model` (expanded, or `File.identical?` when both files exist) and strips the argument. On mismatch the tool does not run and the response is a JSON-RPC error (`-32603`) whose `data` contains `error_type: "wrong_model"`, `expected_model_path`, `active_model_path` (`null` for an unsaved model) and `active_model_title`. The driver injects the argument from `SUPEX_EXPECTED_MODEL` for every tool except `ping`, `console_capture_status`, `reload_extension` and `open_model`.

## REPL Server (`:4433`)

Methods are intentionally minimal:

- `hello`
- `eval`

REPL uses its own JSON-RPC loop and session snippet directory under `.tmp/repl/`.

## VCAD Sidecar (`:9877`)

Uses JSON-RPC with direct methods (`hello`, `ping`, `resources/list`) and `tools/call` for VCAD operations.

Handshake response includes negotiated protocol/capability metadata (for example: data imports, solid imports, fs watch, module tracking).

For schema contracts see:

- `docs/contracts/v1/handshake.schema.json`
- `docs/contracts/v1/tools-call.schema.json`
- `docs/contracts/v1/error-envelope.schema.json`

## Errors

Standard JSON-RPC errors apply (`-32700`, `-32600`, `-32601`, `-32602`, `-32603`).

Supex-specific conventions:

- `-32001` for authentication failures
- VCAD flows frequently return structured envelopes with `error_code` strings (for example `PATH_NOT_ALLOWED`, `PROTOCOL_MISMATCH`, `CAPABILITY_UNAVAILABLE`)

Do not rely on a single numeric code for all path-policy failures across every flow.
