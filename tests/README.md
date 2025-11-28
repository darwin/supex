# Supex E2E Tests

End-to-end tests for the Supex SketchUp automation platform.

## Setup

```bash
cd tests
uv sync
```

## Running Tests

```bash
# Run all e2e tests
uv run pytest e2e/ -v

# Run specific test file
uv run pytest e2e/test_connection.py -v

# Run specific test class
uv run pytest e2e/test_connection.py::TestConnection -v

# Run specific test
uv run pytest e2e/test_connection.py::TestConnection::test_sketchup_status -v

# Run tests by marker
uv run pytest e2e/ -m "not slow" -v
```

## Test Options

```bash
# Skip SketchUp launch (if already running)
uv run pytest e2e/ --no-sketchup-launch

# Keep SketchUp running after tests
uv run pytest e2e/ --no-sketchup-stop

# Both options together (useful for rapid iteration)
uv run pytest e2e/ --no-sketchup-launch --no-sketchup-stop

# Run with custom timeout for slow systems
PYTEST_TIMEOUT=120 uv run pytest e2e/ -v

# Run with output capture disabled (see print statements)
uv run pytest e2e/ -v -s

# Run with detailed failure output
uv run pytest e2e/ -v --tb=long
```

## Test Structure and Strategy

### Architecture

```
tests/
├── conftest.py              # Pytest fixtures and session management
├── pyproject.toml           # Test dependencies and pytest config
├── helpers/
│   ├── sketchup_process.py  # SketchUp process management
│   ├── cli_runner.py        # CLI wrapper for supex commands
│   └── assertions.py        # Custom assertion helpers for JSON validation
├── snippets/
│   └── src/                 # Ruby test snippets (.rb files)
│       ├── loader.rb        # Snippet loader
│       ├── helpers.rb       # Common helpers
│       ├── conftest.rb      # Fixture snippets
│       ├── test_model_operations.rb   # Geometry/groups/materials
│       ├── test_introspection.rb      # Entity listing/selection/camera
│       └── test_error_handling.rb     # Error-inducing snippets
├── data/
│   └── template.skp         # Template model for tests
└── e2e/
    ├── test_connection.py       # Connection and basic communication
    ├── test_model_operations.py # Geometry creation and manipulation
    ├── test_introspection.py    # Model introspection tools
    └── test_error_handling.py   # Error handling and edge cases
```

### Test Organization

Tests follow a four-layer approach:

1. **Connection & Basic Commands** (`test_connection.py`)
   - Validates SketchUp is accessible via TCP
   - Tests basic CLI command execution (parametrized)
   - Verifies SketchUp version and model availability

2. **Model Operations** (`test_model_operations.py`)
   - Tests geometry creation (cubes, circles, cylinders)
   - Tests organizational structures (groups, components)
   - Tests visual properties (materials, colors, transparency)

3. **Model Introspection** (`test_introspection.py`)
   - Tests reading model state (entities, layers, materials)
   - Tests selection operations
   - Tests camera control

4. **Error Handling** (`test_error_handling.py`)
   - Tests Ruby syntax and runtime errors
   - Tests invalid inputs and edge cases
   - Tests error recovery and unicode handling

### Test Execution Flow

1. **Session Start**:
   - pytest loads conftest.py
   - `sketchup` fixture launches SketchUp with template
   - `cli` fixture loads all Ruby snippets
   - `test_model_file` fixture creates initial model file

2. **Per Test**:
   - `fresh_model` fixture clears all entities
   - Test executes Ruby code via CLI or snippets
   - Assertions validate expected state via JSON parsing

3. **Session End**:
   - Model is saved to prevent save dialog
   - SketchUp is gracefully shut down (unless `--no-sketchup-stop`)

### Test Design Principles

- **Isolation**: Each test runs with a clean model (via `fresh_model` fixture)
- **Clarity**: Ruby code extracted to `.rb` files with full IDE support
- **Reliability**: Tests wait for SketchUp startup (up to 60 seconds)
- **Debuggability**: Errors show actual file:line numbers from Ruby sources
- **Structured Assertions**: All snippet outputs are JSON for precise validation

## Test Coverage

### Current Coverage

| Category | Tests | Description |
|----------|-------|-------------|
| Connection | 10 | CLI status, SketchUp communication, parametrized commands |
| Error Handling | 14 | Syntax errors, runtime errors, edge cases, unicode |
| Geometry | 3 | Cube, circle, cylinder creation |
| Groups/Components | 4 | Group creation, nesting, component instances |
| Materials | 4 | Material creation, application, transparency |
| Introspection | 12 | Entity listing, selection, layers, camera |

**Total: 47 tests across 4 test files**

### Pytest Markers

- `error_handling` - Tests for error handling scenarios
- `slow` - Tests that take longer to execute

### Known Gaps

The following areas need additional test coverage:

- File operations (open, save, export with various parameters)
- Large entity count performance
- Connection loss and reconnection
- Transaction rollback on failure
- Advanced camera/view operations
- Complex nested components and groups
- Undo/redo operations

## How It Works

### Key Components

**`sketchup_process.py`** manages SketchUp lifecycle:
- Launches SketchUp with `-RubyStartup` injection
- Loads template from `tests/data/template.skp`
- Waits for TCP connection on port 9876
- Graceful shutdown via AppleScript

**`cli_runner.py`** provides methods for all supex commands:
- `status()`, `info()`, `eval(code)`
- `entities()`, `selection()`, `layers()`, `materials()`
- `screenshot()`, `open_model()`, `save_model()`
- `call_snippet(name)` - Execute Ruby snippets by name
- `json()` method on results for parsing JSON output

**`assertions.py`** provides custom assertion helpers:
- `assert_json_success(result)` - Assert success and parse JSON
- `assert_count(result, key, expected)` - Assert count in JSON
- `assert_name(result, expected)` - Assert name field
- `assert_json_field(result, key, expected)` - Assert any field

**`snippets/`** contains reusable Ruby test code:
- Naming convention: `prefix_action` (e.g., `geom_create_cube`)
- Wrapped in SketchUp operations for proper undo support
- **Returns JSON strings** via `.to_json` for structured assertions

### Available Fixtures

| Fixture | Scope | Description |
|---------|-------|-------------|
| `sketchup` | session | Manages SketchUp process lifecycle |
| `cli` | session | CLI runner with pre-loaded snippets |
| `test_model_file` | session | Path to saved test model |
| `fresh_model` | function | Clean model state for each test |
| `populated_model` | function | Model with pre-created cube geometry |

## Writing New Tests

### Example Test with JSON Assertions

```python
from helpers.cli_runner import CLIRunner

def test_create_cube(fresh_model: CLIRunner) -> None:
    """Create a cube and verify face/edge counts."""
    result = fresh_model.call_snippet("geom_create_cube")
    assert result.success, f"Failed: {result.stderr}"
    data = result.json()
    assert data["faces"] == 6, f"Expected 6 faces, got {data['faces']}"
    assert data["edges"] == 12, f"Expected 12 edges, got {data['edges']}"
```

### Example Test with Inline Ruby

```python
def test_simple_eval(cli: CLIRunner) -> None:
    """Test basic Ruby evaluation."""
    result = cli.eval("1 + 1")
    assert result.success
    assert result.stdout.strip() == "2"
```

### Example Error Handling Test

```python
def test_runtime_error(cli: CLIRunner) -> None:
    """Ruby runtime error should be reported."""
    result = cli.eval("raise 'Test error'")
    assert not result.success
    # Error messages may appear in stdout or stderr
    output = result.stdout + result.stderr
    assert "Test error" in output
```

### Adding New Ruby Snippets

1. Add function to module in `snippets/src/*.rb`
2. Name with appropriate prefix (`geom_`, `group_`, `material_`, `error_`)
3. Wrap in `start_operation`/`commit_operation`
4. **Return JSON string** via `.to_json` for structured assertions

```ruby
# snippets/src/test_model_operations.rb
require 'json'

# Creates a sphere and returns face count as JSON.
# @return [String] JSON: {"faces": N}
def self.geom_create_sphere
  model = Sketchup.active_model
  model.start_operation('Create Sphere', true)

  # Create sphere geometry...

  model.commit_operation
  { faces: model.entities.grep(Sketchup::Face).length }.to_json
end
```

### Best Practices

1. **Use `fresh_model` fixture** - Ensures clean state for each test
2. **Use `populated_model` fixture** - When you need pre-existing geometry
3. **Wrap operations** - Always use `start_operation`/`commit_operation`
4. **Return JSON from snippets** - Use `.to_json` for structured data
5. **Parse with `result.json()`** - Get dict from JSON output
6. **Use specific assertions** - Compare exact values, not substrings
7. **Include error context** - Use `assert condition, f"message: {details}"`

## Common Test Patterns

### Pattern 1: Create and Verify via JSON

```python
result = fresh_model.call_snippet('geom_create_cube')
assert result.success
data = result.json()
assert data["faces"] == 6
assert data["edges"] == 12
```

### Pattern 2: Create and Inspect via Command

```python
fresh_model.call_snippet('material_create_blue')
result = fresh_model.materials()
assert result.success
```

### Pattern 3: Verify State Changes

```python
before = fresh_model.info()
fresh_model.call_snippet('geom_add_face')
after = fresh_model.info()
# Compare entity counts between before and after
```

### Pattern 4: Test Error Conditions

```python
result = cli.eval("raise 'Intentional error'")
assert not result.success
# Check both stdout and stderr for error message
output = result.stdout + result.stderr
assert "Intentional error" in output
```

### Pattern 5: Parametrized Tests

```python
import pytest

@pytest.mark.parametrize("command", ["info", "camera", "layers", "materials"])
def test_basic_command_succeeds(cli: CLIRunner, command: str) -> None:
    """Basic CLI commands should execute successfully."""
    method = getattr(cli, command)
    result = method()
    assert result.success
```

## Troubleshooting

### Welcome Screen Appears on Startup

**Problem:** SketchUp shows the Welcome screen instead of opening a model directly.

**Solution:** Disable the Welcome screen in SketchUp preferences:

1. Open SketchUp
2. Go to **Window > Preferences** (or **SketchUp > Settings** on macOS)
3. Select **General** section
4. Uncheck **Show Welcome Window on Startup**
5. Click **OK**

Reference: [SketchUp Forums - Welcome screen instead of open file](https://forums.sketchup.com/t/welcome-screen-instead-of-open-file/231846)

### SketchUp Not Starting

**Symptoms:**
```
TimeoutError: SketchUp did not become ready within 60 seconds
```

**Possible causes:**
1. SketchUp is already running - close it manually
2. Port 9876 is in use - check with `lsof -i :9876`
3. Extension failed to load - check `.tmp/sketchup_console.log`

**Solution:**
```bash
# Kill any running SketchUp instances
pkill -9 SketchUp

# Check if port is free
lsof -i :9876

# Run tests with verbose output
uv run pytest e2e/ -v -s
```

### Connection Refused

**Symptoms:**
```
SketchUpConnectionError: Connection refused
```

**Possible causes:**
1. Extension not loaded properly
2. Server failed to start on port 9876
3. Firewall blocking localhost connections

**Solution:**
1. Check console log: `cat .tmp/sketchup_console.log`
2. Verify extension is loaded: Check **Extensions** menu in SketchUp
3. Test connection manually: `./supex status` (from repository root)

### Tests Fail with "Model Not Empty"

**Problem:** Tests expect empty model but entities already exist.

**Solution:** The `fresh_model` fixture should handle this. If it fails:
```bash
# Clear model manually via CLI (from repository root)
./supex eval "Sketchup.active_model.entities.clear!"
```

### Template File Missing

**Symptoms:**
```
FileNotFoundError: Template file not found: tests/data/template.skp
```

**Solution:** Create a template file:
1. Open SketchUp
2. Create new model with desired settings (Architectural Millimeters)
3. Save empty model to `tests/data/template.skp`

### Fixture-Related Failures

**Problem:** `fresh_model` fixture fails or tests run with stale state.

**Solution:**
1. Verify snippet loading: check `.tmp/sketchup_console.log` for Ruby errors
2. Ensure `template.skp` exists and is valid
3. Try running with `--no-sketchup-launch` if SketchUp is already clean

### Ruby Code Errors

**Problem:** Tests fail with Ruby exceptions.

**Debugging:**
- Stack traces show actual file:line from `.rb` files
- Check Ruby version compatibility (Ruby 3.4 for SketchUp 2026)
- Verify SketchUp API version matches expectations
- Review `.tmp/sketchup_console.log` for detailed errors

### JSON Parsing Errors

**Problem:** `result.json()` fails with parsing error.

**Causes:**
- Ruby snippet doesn't return valid JSON
- Missing `require 'json'` in Ruby file
- Snippet returns Ruby hash instead of JSON string

**Solution:**
- Ensure snippet ends with `.to_json`
- Check `result.stdout` to see actual output
- Verify Ruby file has `require 'json'` at top

### Assertion Failures with Entity Counts

**Problem:** Entity counts don't match expected values.

**Causes:**
- Some SketchUp operations create additional geometry internally
- Model may have hidden or soft edges
- Groups/components may contain nested entities

**Solution:**
- Use `>=` instead of `==` for counts when appropriate
- Log actual values for debugging: `print(result.json())`
- Use introspection commands to understand model state

## CI/CD Considerations

These tests require:
- macOS (for SketchUp)
- SketchUp installed
- Display/windowing system (not headless)
- Welcome screen disabled in preferences

For CI environments, consider:
- Using a pre-configured SketchUp installation
- Running on macOS agents with GUI support
- Caching SketchUp installation and preferences
- Setting appropriate timeouts for slower CI runners
