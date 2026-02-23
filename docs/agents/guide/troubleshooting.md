# Troubleshooting

Common issues and solutions when using Supex.

## Connection Issues

### Connection Refused

**Symptom**: `SketchUpConnectionError: Connection refused`

**Causes**:
1. SketchUp is not running
2. Supex extension is not loaded
3. Bridge server did not start

**Solutions**:
1. Launch SketchUp with `./scripts/launch-sketchup.sh`
2. Check Ruby Console in SketchUp for extension errors
3. Verify server started: look for "Bridge server started and listening" in SketchUp console
4. Check if `SUPEX_NO_AUTOSTART=1` is set (disables automatic server start)

### Port Already in Use

**Symptom**: `Address already in use - bind(2) for "127.0.0.1" port 9876`

**Causes**:
1. Another SketchUp instance is running
2. Previous server did not shut down cleanly
3. Another application is using port 9876

**Solutions**:
1. Close other SketchUp instances
2. Wait a few seconds for the port to be released
3. Check what is using the port: `lsof -i :9876`

### Timeout Errors

**Symptom**: `SketchUpTimeoutError: Socket read timeout`

**Causes**:
1. SketchUp is busy with a long operation
2. Ruby code execution is taking too long
3. Network issues (rare for localhost)

**Solutions**:
1. Increase timeout: `SUPEX_TIMEOUT=30`
2. Break long operations into smaller chunks
3. Check SketchUp is responsive (can you interact with the UI?)

## Authentication Errors

### Authentication Failed (-32001)

**Symptom**: Error code -32001, "Authentication failed: invalid or missing token"

**Causes**:
1. Server has `SUPEX_AUTH_TOKEN` set, but client is not sending it
2. Token mismatch between client and server
3. Token not set in the environment where driver runs

**Solutions**:
1. Ensure same `SUPEX_AUTH_TOKEN` is set for both SketchUp and the driver
2. For CLI: `SUPEX_AUTH_TOKEN=mytoken ./supex status`
3. For MCP: set the token in your shell environment before running

## Path Access Errors

### Path Access Denied

**Symptom**: Message containing "Path access denied" or structured `PATH_NOT_ALLOWED`

**Causes**:
1. Trying to access a file outside allowed roots
2. `SUPEX_WORKSPACE` not set in MCP client env config
3. Path traversal attempt (e.g., `../../etc/passwd`)

**Solutions**:
1. Set `SUPEX_WORKSPACE` in your MCP client's environment configuration
2. Add additional paths to `SUPEX_ALLOWED_ROOTS` (colon-separated)
3. Use absolute paths within allowed directories
4. Disable restrictions (not recommended): `SUPEX_ALLOWED_ROOTS=*`

## REPL Issues

### REPL Not Responding

**Symptom**: REPL client connects but commands hang

**Causes**:
1. SketchUp UI is blocked (modal dialog open)
2. Previous command is still executing
3. Timer-based polling is not running

**Solutions**:
1. Close any open dialogs in SketchUp
2. Wait for current operation to complete
3. Restart SketchUp if unresponsive

### REPL Server Disabled

**Symptom**: Cannot connect to REPL port 4433

**Causes**:
1. `SUPEX_REPL_DISABLED=1` is set
2. REPL is using a different port

**Solutions**:
1. Remove `SUPEX_REPL_DISABLED` from environment
2. Check `SUPEX_REPL_PORT` setting

## Finding Logs

Log files are written under `$SUPEX_LOG_DIR`.

When using repository wrappers, the default is `$SUPEX_WORKSPACE/.tmp/logs`.

**Wrapper logs**:
- `$SUPEX_LOG_DIR/supex-cli-stdout.log`
- `$SUPEX_LOG_DIR/supex-cli-stderr.log`
- `$SUPEX_LOG_DIR/supex-mcp-protocol.jsonl`
- `$SUPEX_LOG_DIR/supex-mcp-stderr.log`
- `$SUPEX_LOG_DIR/vcad-sidecar-stderr.log`

**Driver internal log**:
- `$SUPEX_LOG_DIR/supex-cli.log`

**Runtime logs**:
- SketchUp Ruby Console
- `./.tmp/sketchup_console.log` (console capture)

**Request tracing**:
- Each request includes an ID like `[req:123]`
- Search this ID across CLI/MCP/runtime logs

## Export Issues

### `export dae` fails

`dae` is not supported by the SketchUp runtime export tool.

Use one of:
- `skp`
- `obj`
- `stl`
- `png`
- `jpg`
- `jpeg`

## VCAD Issues

### Sidecar Not Starting

Check the binary exists:

```bash
ls vcad/sidecar/target/release/supex-vcad-sidecar
```

If missing, build it:

```bash
cargo build --release --manifest-path vcad/sidecar/Cargo.toml
```

### Connection Refused on Port 9877

The sidecar is not running. Start it:

```bash
./vcad-sidecar
```

If it crashes, inspect logs:

```bash
cat .tmp/logs/vcad-sidecar-stderr.log
```

### PATH_NOT_ALLOWED

The sidecar enforces workspace path containment.

- Set `SUPEX_WORKSPACE` to your project root
- Keep VCAD source files inside the workspace
- Avoid `..` traversal segments in source file paths

### AUTH_INVALID

Token mismatch between driver and sidecar.

- Ensure `SUPEX_VCAD_AUTH_TOKEN` is set consistently in both environments
- If binding remotely, also set `SUPEX_VCAD_ALLOW_REMOTE=1`

### Non-Loopback Bind Fails

The sidecar requires both:

- `SUPEX_VCAD_ALLOW_REMOTE=1`
- `SUPEX_VCAD_AUTH_TOKEN` (non-empty)

Without both values, remote bind is rejected.

### DAE Import Fails in SketchUp

- Verify the generated DAE exists and is non-empty
- Confirm SketchUp is running and runtime is loaded
- Check SketchUp console output for Ruby import errors

### Stale Geometry After Update

If geometry looks outdated after edit/update:

1. Check `vcad_list_nodes()` versions
2. Run `vcad_update()` explicitly
3. Review `.supex/vcad-state.json` for revision drift

### SOLID_IMPORT_UNAVAILABLE

`:solid` imports require either:

- A VCAD-backed entity (`vcad_node_id` attribute)
- A native SketchUp Group/ComponentInstance with valid face geometry

If neither applies, import fails.

### ADT_CACHE_MISS

When importing `:solid` from another VCAD node, the source node must be evaluated first.

- Run `vcad_update(<source-node>)`
- Or use `vcad_update_cascade(<upstream-node>)`

## Common Ruby Errors

### NoMethodError

**Symptom**: Error code -32000 with "undefined method"

**Cause**: Calling a method that does not exist on an object

**Solution**: Check the SketchUp Ruby API documentation for correct method names

### TypeError

**Symptom**: Error code -32000 with "wrong argument type"

**Cause**: Passing incorrect argument types to SketchUp API

**Solution**: Verify argument types match the API documentation

### ModelObserver errors

**Symptom**: Errors about observers or callbacks

**Cause**: Modifying model state during observer callbacks

**Solution**: Use `model.start_operation` / `model.commit_operation` to batch changes

## Diagnostic Commands

Check connection status:
```bash
./supex status
```

Get detailed model information:
```bash
./supex info
```

Test Ruby execution:
```bash
./supex eval "Sketchup.version"
```

## Getting Help

1. Check Configuration docs for all environment variables
2. Review Protocol docs for message format details
3. See Security docs for authentication and path policy
4. Report issues at: <https://github.com/darwin/supex/issues>
