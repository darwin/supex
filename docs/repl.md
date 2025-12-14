# Interactive REPL

The REPL (Read-Eval-Print Loop) provides interactive Ruby development directly in SketchUp's context. It runs as a separate TCP server (JSON-RPC 2.0 protocol) alongside the MCP bridge, allowing you to experiment with Ruby code in real-time.

## Quick Start

1. Launch SketchUp with the Supex extension (REPL server starts automatically)
2. Connect from your terminal:

```bash
./repl
```

3. Start typing Ruby code:

```
supex>> Sketchup.active_model.entities.length
=> 42
supex>> model = Sketchup.active_model
=> #<Sketchup::Model:0x00007f8b8c0b8e00>
supex>> model.selection.clear
=> []
```

4. Exit with `exit` or Ctrl+D

## Client Modes

### Simple Mode (Default)

The default mode uses Ruby's Readline for a straightforward line-by-line interface:

```bash
./repl
# or explicitly:
./repl --simple
```

Features:
- Readline-based input with history
- Duplicate history entries are automatically removed
- Clean error messages with stack traces
- Exit via `exit` command or Ctrl+D

### Pry Mode

For advanced users and IDE integration, Pry mode provides a richer experience:

```bash
./repl --pry
```

Features:
- Full Pry REPL interface
- Syntax highlighting
- RubyMine compatible (can be configured as external tool)
- Code is sent to SketchUp via monkey-patched eval

Note: Requires the `pry` gem. In the repository, run `bundle install` in the `runtime/` directory. Outside the repository, use `gem install pry`.

### RubyMine Integration

RubyMine has built-in support for Ruby REPL and is Pry-aware. You can configure a Run Configuration to use Supex REPL with full IDE integration.

**Prerequisites:**

Add `pry` to your project's Gemfile and install:

```ruby
# Gemfile
gem 'pry'
```

```bash
bundle install
```

**Setup:**

1. Open **Run > Edit Configurations**
2. Click **+** and select **Ruby Console**
3. On the **Configuration** tab:
   - **Name**: `Supex REPL`
   - **Console script**: Path to pry (run `bundle show pry` then use `bin/pry` in that path, or simply `pry` if globally installed)
   - **Console script arguments**: `-r /path/to/supex/runtime/src/repl.rb`
   - **Working directory**: Your project root
   - **Ruby SDK**: Use project SDK
4. On the **Bundler** tab:
   - Check **Run the script in context of the bundle (bundle exec)**
5. Click **OK** to save

The `-r` flag loads the REPL client code that monkey-patches Pry to send commands to SketchUp.

**Usage:**

1. Ensure SketchUp is running with Supex extension loaded
2. Run the "Supex REPL" configuration from RubyMine
3. Use **Tools > Load File/Selection into IRB Console** to send code to SketchUp

**Tips:**

- Configure a keyboard shortcut for **Tools > Load File/Selection into IRB Console** (e.g., `Ctrl+Shift+Enter`) in **Settings > Keymap**
- Ruby files must be part of RubyMine's project content root for "Load File into Console" to work
- Ensure your Ruby SDK version matches SketchUp's bundled Ruby (3.2.2 for SketchUp 2026)

## Command-Line Options

| Option | Description |
|--------|-------------|
| `-p`, `--port PORT` | REPL server port (default: 4433) |
| `-h`, `--host HOST` | REPL server host (default: 127.0.0.1) |
| `--pry` | Use Pry mode with monkey-patched eval |
| `--simple` | Use simple line-by-line mode (default) |
| `--help` | Show help message |

Examples:

```bash
./repl                    # Default settings
./repl -p 5000            # Connect to port 5000
./repl -h 192.168.1.100   # Connect to remote host
./repl --pry              # Use Pry mode
```

## Configuration

The REPL can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPEX_REPL_PORT` | `4433` | Server port |
| `SUPEX_REPL_HOST` | `127.0.0.1` | REPL client default host |
| `SUPEX_REPL_DISABLED` | (unset) | Disable REPL server (set to `1`) |
| `SUPEX_REPL_BUFFER_MS` | `50` | Input buffer timeout for IDE paste detection |

See [Configuration](configuration.md) for all environment variables.

## REPL vs eval_ruby

Supex provides two ways to execute Ruby code in SketchUp:

| Feature | REPL (`./repl`) | MCP (`eval_ruby`) |
|---------|-----------------|-------------------|
| **Use case** | Interactive exploration | AI-driven automation |
| **Interface** | Terminal prompt | MCP protocol |
| **Binding** | TOPLEVEL_BINDING | Fresh binding per call |
| **Best for** | Quick tests, debugging | Scripts, batch operations |
| **State** | Persistent session | Each call is independent |

**When to use REPL:**
- Exploring SketchUp API interactively
- Quick one-off commands
- Debugging and troubleshooting
- Learning the API

**When to use eval_ruby:**
- AI-assisted development (Claude Code)
- Automated scripts
- Reproducible operations
- Integration with MCP tools

## Server Control

The REPL server starts automatically with the Supex extension. You can control it via:

**SketchUp Menu:**
- Extensions > Supex > Start REPL
- Extensions > Supex > Stop REPL

**Disable at Startup:**

```bash
SUPEX_REPL_DISABLED=1 ./scripts/launch-sketchup.sh
```

## Troubleshooting

### Connection Refused

```
Error: Cannot connect to REPL server at 127.0.0.1:4433
```

- Ensure SketchUp is running with the Supex extension loaded
- Check if REPL server is disabled (`SUPEX_REPL_DISABLED=1`)
- Verify the port is not in use by another application
- Try starting REPL server from SketchUp menu

### Pry Not Found

```
Error: Pry gem not found. Install it with: gem install pry
```

Install Pry in your Ruby environment:

```bash
gem install pry
```

### Connection Lost

```
Error: Connection lost. Server may have stopped.
```

- SketchUp may have crashed or been closed
- REPL server may have been stopped from the menu
- Restart SketchUp and reconnect
