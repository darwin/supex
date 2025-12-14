# Configuration

Supex can be configured via environment variables:

## Security

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_AUTH_TOKEN` | (unset) | Shared authentication token for Bridge and REPL servers |
| `SUPEX_ALLOW_REMOTE` | (unset) | Allow binding to non-loopback addresses (set to `1`) |
| `SUPEX_ALLOWED_ROOTS` | (unset) | Colon-separated list of allowed file path roots |
| `SUPEX_WORKSPACE` | (unset) | User project directory (passed to runtime via hello handshake) |

**Authentication**: When `SUPEX_AUTH_TOKEN` is set, clients must provide this token in the `hello` handshake to connect. Without a valid token, the server returns error code `-32001`.

**Remote binding**: By default, servers only bind to loopback addresses (`127.0.0.1`, `localhost`, `::1`). To allow binding to non-loopback addresses, set `SUPEX_ALLOW_REMOTE=1`. When binding remotely without a token, a security warning is logged.

**Path restrictions**: File operations (`eval_ruby_file`, `open_model`, `save_model`, `take_screenshot`) are restricted to:
- Paths within `SUPEX_WORKSPACE` (passed from MCP client via hello handshake)
- Additional paths specified in `SUPEX_ALLOWED_ROOTS` (colon-separated)

Note: Path restrictions are a guardrail to prevent accidental writes to wrong directories, not a security boundary (arbitrary Ruby execution bypasses them).

**Workspace configuration**: Set `SUPEX_WORKSPACE` in your MCP client's environment configuration. Default screenshot paths (when `output_path` is not specified) will be saved to `$SUPEX_WORKSPACE/.tmp/screenshots/`.

Example MCP client configuration:
```json
{
  "mcpServers": {
    "supex": {
      "command": "/path/to/supex/mcp",
      "env": {
        "SUPEX_WORKSPACE": "/path/to/your-project"
      }
    }
  }
}
```

To disable path restrictions, set `SUPEX_ALLOWED_ROOTS=*`.

## Bridge Server (MCP)

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_HOST` | `localhost` | SketchUp runtime host (driver/CLI connects to this) |
| `SUPEX_PORT` | `9876` | SketchUp runtime port (driver/CLI connects to this) |
| `SUPEX_TIMEOUT` | `15.0` | Socket timeout in seconds |
| `SUPEX_RETRIES` | `2` | Max retry attempts |
| `SUPEX_IDLE_TIMEOUT` | `300` | Connection idle timeout in seconds (driver reconnects after this) |
| `SUPEX_LOG_DIR` | `~/.supex/logs` | Driver log directory |
| `SUPEX_VERBOSE` | (unset) | Enable runtime verbose logging (set to `1`) |
| `SUPEX_AGENT` | (auto) | Agent identifier for logging |
| `SUPEX_NO_AUTOSTART` | (unset) | Disable automatic server start on extension load (set to `1`) |
| `SUPEX_CHECK_INTERVAL` | `0.25` | Request check interval in seconds |
| `SUPEX_RESPONSE_DELAY` | `0` | Response delay in seconds (for debugging) |

## Standard Library

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_STDLIB_PATH` | (auto) | Custom path to stdlib directory |

## REPL Server

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_REPL_PORT` | `4433` | REPL server port |
| `SUPEX_REPL_HOST` | `127.0.0.1` | REPL client default host |
| `SUPEX_REPL_DISABLED` | (unset) | Disable REPL server (set to `1`) |
| `SUPEX_REPL_BUFFER_MS` | `50` | Input buffer timeout for IDE paste detection |

See [Interactive REPL](repl.md) for usage details.
