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
3. Verify server started: look for "Bridge server started on port 9876" in SketchUp console
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
3. Use a different port: `SUPEX_PORT=9877`
4. Check what is using the port: `lsof -i :9876`

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

### Path Access Denied (-32002)

**Symptom**: Error code -32002, "Path access denied"

**Causes**:
1. Trying to access a file outside allowed roots
2. `SUPEX_PROJECT_ROOT` not set or incorrect
3. Path traversal attempt (e.g., `../../etc/passwd`)

**Solutions**:
1. Set `SUPEX_PROJECT_ROOT` to your project directory
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

Log files are stored in `~/.supex/logs/` by default. You can change this with `SUPEX_LOG_DIR`.

**Driver logs**:
- Located at `$SUPEX_LOG_DIR/supex.log`
- Contains connection attempts, requests, and errors
- Enable verbose logging: `SUPEX_VERBOSE=1`

**Runtime logs**:
- Visible in SketchUp's Ruby Console
- Check Window > Ruby Console in SketchUp

**Request tracing**:
- Each request has a unique ID in logs: `[req:123]`
- Search for this ID to trace a request through driver and runtime

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

1. Check the [Configuration](configuration.md) for all environment variables
2. Review the [Protocol](protocol.md) for message format details
3. See [Security](security.md) for authentication and path policy
4. Report issues at: https://github.com/darwin/supex/issues
