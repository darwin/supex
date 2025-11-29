# Configuration

Supex can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_HOST` | `localhost` | Server bind address |
| `SUPEX_PORT` | `9876` | Server port |
| `SUPEX_TIMEOUT` | `15.0` | Socket timeout in seconds |
| `SUPEX_RETRIES` | `2` | Max retry attempts |
| `SUPEX_LOG_DIR` | `~/.supex/logs` | Log directory |
| `SUPEX_VERBOSE` | (unset) | Enable verbose logging (set to `1`) |
| `SUPEX_AGENT` | (auto) | Agent identifier for logging |
