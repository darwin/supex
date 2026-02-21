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

## vcad Sidecar

The vcad Rust sidecar evaluates Loon CAD code and produces BRep geometry. See [vcad Integration](vcad.md) for full documentation.

### Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `VCAD_HOST` | `127.0.0.1` | Sidecar bind/connect host |
| `VCAD_PORT` | `9877` | Sidecar TCP port |
| `VCAD_TIMEOUT` | `30` | Request timeout in seconds |
| `VCAD_SIDECAR_PATH` | (auto) | Path to sidecar binary (auto-detected from repo) |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `VCAD_AUTH_TOKEN` | (unset) | Authentication token (required when `VCAD_ALLOW_REMOTE=1`) |
| `VCAD_ALLOW_REMOTE` | `0` | Allow non-loopback bind (requires `VCAD_AUTH_TOKEN`) |

**Non-loopback binding**: The sidecar refuses to bind to non-loopback addresses unless both `VCAD_ALLOW_REMOTE=1` and `VCAD_AUTH_TOKEN` are set. This prevents unauthenticated remote access to the evaluation engine.

### Evaluation

| Variable | Default | Description |
|----------|---------|-------------|
| `VCAD_MAX_QUEUE` | `64` | Maximum queued eval jobs |
| `VCAD_EVAL_TIMEOUT_MS` | `120000` | Max wait per queued eval request in milliseconds |
| `VCAD_ADT_CACHE_MAX` | `256` | Max entries in ADT cache (LRU eviction) |

### Temp Files

| Variable | Default | Description |
|----------|---------|-------------|
| `VCAD_TEMP_DIR` | (system temp) | Directory for OBJ and manifest files |
| `VCAD_TEMP_TTL_SEC` | `3600` | Max age of temp artifact files in seconds |
| `VCAD_TEMP_MAX_FILES` | `500` | Max number of retained artifact sets (OBJ + manifest) |

### Driver State

| Variable | Default | Description |
|----------|---------|-------------|
| `VCAD_STATE_PATH` | `<workspace>/.supex/vcad-state.json` | Persisted driver state file |
