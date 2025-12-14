# Security

Supex is designed for local development use. This document describes the security features and recommendations.

## Threat Model

Supex exposes Ruby code execution capabilities over TCP sockets. The primary threats are:

1. **Unauthorized access**: Other local processes connecting to the server
2. **Path traversal**: Accessing files outside intended directories
3. **State pollution**: Interference between eval calls

## Network Security

### Localhost-Only Binding

By default, both Bridge and REPL servers bind only to loopback addresses (`127.0.0.1`, `localhost`, `::1`). This prevents network access from other machines.

To allow binding to non-loopback addresses (not recommended):

```bash
export SUPEX_ALLOW_REMOTE=1
```

When binding to non-loopback addresses without authentication, a security warning is logged.

### Authentication Token

Set a shared token to require authentication for all connections:

```bash
# On the machine running SketchUp
export SUPEX_AUTH_TOKEN=your-secret-token

# When using the driver/CLI
export SUPEX_AUTH_TOKEN=your-secret-token
./supex status
```

With authentication enabled:
- Clients must provide the token in the `hello` handshake
- Invalid or missing tokens result in error code `-32001`
- The connection is rejected immediately

**Recommendations**:
- Always use authentication when binding to non-loopback addresses
- Use a strong, random token (e.g., `openssl rand -hex 32`)
- Do not commit tokens to version control

## File Path Security

### Path Allowlist

File operations (`eval_ruby_file`, `open_model`, `save_model`, `take_screenshot`) are restricted to specific directories.

**Default allowed paths**:
- repository `.tmp/` directory

**Configure allowed paths**:

```bash
# Set project root (recommended for most use cases)
export SUPEX_PROJECT_ROOT=/path/to/your/project

# Add additional allowed paths (colon-separated)
export SUPEX_ALLOWED_ROOTS=/path/one:/path/two
```

### Path Validation

The path policy:
1. Resolves symlinks to prevent symlink escape attacks
2. Checks that the resolved path starts with an allowed root
3. Rejects paths containing `..` traversal attempts

**Error handling**: Attempts to access paths outside allowed roots result in error code `-32002`.

### Disabling Restrictions

To disable path restrictions entirely (not recommended):

```bash
export SUPEX_ALLOWED_ROOTS=*
```

This is useful for debugging but should not be used in shared environments.

## Code Execution Isolation

### Eval Binding Isolation

Each `eval_ruby` call executes in a fresh binding context. This means:
- Local variables from one eval do not persist to the next
- Instance variables on the binding object are not shared
- Global variables and constants do persist (Ruby limitation)

### What Is Not Isolated

- Global variables (`$foo`)
- Constants defined at top level
- Modifications to existing classes/modules
- SketchUp model state
- File system changes

### Recommendations

- Avoid relying on state between eval calls
- Clean up after operations that create global state
- Use `Sketchup.undo` to revert model changes during development

## Operational Security

### Running in Production

Supex is designed for development, not production deployment. If you must run it in a shared environment:

1. Always enable authentication (`SUPEX_AUTH_TOKEN`)
2. Keep binding to localhost only
3. Configure minimal path allowlists
4. Monitor the SketchUp process for unusual activity

### Firewall Recommendations

Even with localhost binding, consider:
- Blocking ports 9876 and 4433 from external access
- Using application-level firewalls to restrict which processes can connect

### Logging and Auditing

Enable verbose logging to track all operations:

```bash
export SUPEX_VERBOSE=1      # Runtime verbose logging
export SUPEX_LOG_DIR=/var/log/supex  # Driver log directory
```

Logs include:
- Connection attempts (with agent identifier)
- All method calls with request IDs
- Error conditions and authentication failures

## Security Checklist

For local development (default):
- [ ] Using localhost binding (default)
- [ ] Path restrictions configured via `SUPEX_PROJECT_ROOT`

For shared environments:
- [ ] `SUPEX_AUTH_TOKEN` set with a strong random value
- [ ] `SUPEX_PROJECT_ROOT` and `SUPEX_ALLOWED_ROOTS` configured
- [ ] Firewall rules in place
- [ ] Logging enabled

## Related Documentation

- [Configuration](configuration.md) - All environment variables
- [Protocol](protocol.md) - Authentication in the hello handshake
- [Troubleshooting](troubleshooting.md) - Authentication error handling
