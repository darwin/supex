# Configuration

Supex behavior is controlled primarily through environment variables.

## Security and Path Policy

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_AUTH_TOKEN` | (unset) | Shared token for Bridge + REPL authentication |
| `SUPEX_ALLOW_REMOTE` | `0` | Allow non-loopback bind when set to `1` |
| `SUPEX_ALLOWED_ROOTS` | (unset) | Colon-separated path allowlist for guarded file operations |
| `SUPEX_WORKSPACE` | wrapper-dependent | Workspace root passed to runtime in `hello` handshake |

Path policy is a guardrail, not a sandbox. Arbitrary Ruby execution can bypass it.

## Wrapper Defaults

Workspace defaults differ by entrypoint script:

- `./supex`: `SUPEX_WORKSPACE=${SUPEX_WORKSPACE:-$HOME/.supex/tmp-workspace}`
- `./mcp`: `SUPEX_WORKSPACE=${SUPEX_WORKSPACE:-$(pwd)}`
- `./vcad-sidecar`: `SUPEX_WORKSPACE=${SUPEX_WORKSPACE:-$(pwd)}`

## Bridge / Driver (MCP + CLI)

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_HOST` | `localhost` | SketchUp runtime host |
| `SUPEX_PORT` | `9876` | SketchUp runtime port |
| `SUPEX_TIMEOUT` | `15.0` | Socket timeout in seconds |
| `SUPEX_RETRIES` | `2` | Retry count on connection failure |
| `SUPEX_IDLE_TIMEOUT` | `300` | Reconnect after idle seconds |
| `SUPEX_MAX_RESPONSE` | `10485760` | Max response payload bytes |
| `SUPEX_LOG_DIR` | `$SUPEX_WORKSPACE/.tmp/logs` | CLI/MCP log directory |
| `SUPEX_AGENT` | auto | Agent identifier for logs/handshake |
| `SUPEX_VERBOSE` | (unset) | Verbose runtime logging when set to `1` |
| `SUPEX_NO_AUTOSTART` | (unset) | Disable extension autostart when set to `1` |
| `SUPEX_CHECK_INTERVAL` | `0.25` | Runtime request poll interval (seconds) |
| `SUPEX_RESPONSE_DELAY` | `0` | Artificial response delay (seconds) |
| `SUPEX_PLAIN` | (unset) | Force plain-text CLI output when set to `1` |
| `SUPEX_COLOR` | (unset) | Force rich/color CLI output when set to `1` |

## REPL

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_REPL_PORT` | `4433` | REPL server port |
| `SUPEX_REPL_HOST` | `127.0.0.1` | REPL client default host |
| `SUPEX_REPL_DISABLED` | (unset) | Disable runtime REPL server when set to `1` |
| `SUPEX_REPL_BUFFER_MS` | `50` | Pry input coalescing window |
| `SUPEX_REPL_RETRIES` | `10` | REPL client reconnect attempts |

## VCAD Driver Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_VCAD_HOST` | `localhost` | VCAD sidecar host used by driver |
| `SUPEX_VCAD_PORT` | `9877` | VCAD sidecar port used by driver |
| `SUPEX_VCAD_TIMEOUT` | `30.0` | Driver-side VCAD timeout (seconds) |
| `SUPEX_VCAD_RETRIES` | `2` | Driver-side VCAD reconnect attempts |
| `SUPEX_VCAD_IDLE_TIMEOUT` | `300` | VCAD reconnect after idle seconds |
| `SUPEX_VCAD_MAX_RESPONSE` | `10485760` | Max VCAD response payload bytes |
| `SUPEX_VCAD_SIDECAR_PATH` | auto-detected | Sidecar binary path override |
| `SUPEX_VCAD_VIEWER_RELAY_PORT` | `9878` | Driver-side WebSocket relay port for VCAD viewer |

## VCAD Reactive Update Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_VCAD_TRIGGER_COALESCE_MS` | `150` | Coalescing window for merged reactive VCAD updates |
| `SUPEX_VCAD_OBSERVER_POLL_MS` | `250` | SketchUp observer polling interval for reactive updates |

## VCAD Sidecar Runtime

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_VCAD_HOST` | `127.0.0.1` | Sidecar bind host |
| `SUPEX_VCAD_PORT` | `9877` | Sidecar bind port |
| `SUPEX_VCAD_ALLOW_REMOTE` | `0` | Allow non-loopback bind (requires auth token) |
| `SUPEX_VCAD_AUTH_TOKEN` | (unset) | Required for remote bind/authenticated usage |
| `SUPEX_VCAD_TEMP_DIR` | `$SUPEX_WORKSPACE/.tmp/vcad-sidecar` | Artifact directory |
| `SUPEX_VCAD_TEMP_TTL_SEC` | `3600` | Artifact TTL (seconds) |
| `SUPEX_VCAD_TEMP_MAX_FILES` | `500` | Max retained artifacts |
| `SUPEX_VCAD_MAX_QUEUE` | `64` | Eval queue capacity |
| `SUPEX_VCAD_EVAL_TIMEOUT_MS` | `120000` | Eval timeout per request |
| `SUPEX_VCAD_ADT_CACHE_MAX` | `256` | ADT cache capacity |
| `SUPEX_VCAD_STATE_PATH` | `<workspace>/.supex/vcad-state.json` | Driver state persistence path |

If neither `SUPEX_VCAD_TEMP_DIR` nor `SUPEX_WORKSPACE` is set, sidecar startup fails.

## Log Files

All logs are written under a single canonical root: `$SUPEX_WORKSPACE/.tmp/logs/`

(Override with `$SUPEX_LOG_DIR` for wrappers.)

- `cli-stdout.log`
- `cli-stderr.log`
- `cli-driver.log`
- `mcp-protocol.jsonl`
- `mcp-stderr.log`
- `vcad-sidecar-stderr.log`
- `runtime-console.log`
- `runtime-stdout.log`
- `runtime-stderr.log`
