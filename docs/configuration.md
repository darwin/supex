# Configuration

Supex can be configured via environment variables:

## Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_AUTH_TOKEN` | (unset) | Shared authentication token for Bridge and REPL servers |

When set, clients must provide this token in the `hello` handshake to connect. Without a valid token, the server returns error code `-32001`.

## Bridge Server (MCP)

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_HOST` | `localhost` | Server bind address |
| `SUPEX_PORT` | `9876` | Server port |
| `SUPEX_TIMEOUT` | `15.0` | Socket timeout in seconds |
| `SUPEX_RETRIES` | `2` | Max retry attempts |
| `SUPEX_LOG_DIR` | `~/.supex/logs` | Log directory |
| `SUPEX_VERBOSE` | (unset) | Enable verbose logging (set to `1`) |
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
| `SUPEX_REPL_HOST` | `127.0.0.1` | REPL server bind address |
| `SUPEX_REPL_DISABLED` | (unset) | Disable REPL server (set to `1`) |
| `SUPEX_REPL_BUFFER_MS` | `50` | Input buffer timeout for IDE paste detection |

See [Interactive REPL](repl.md) for usage details.
