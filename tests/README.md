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

# Run specific test
uv run pytest e2e/test_connection.py::TestConnection::test_sketchup_status -v
```

## Test Options

```bash
# Skip SketchUp launch (if already running)
uv run pytest e2e/ --no-sketchup-launch

# Keep SketchUp running after tests
uv run pytest e2e/ --no-sketchup-stop

# Both options together
uv run pytest e2e/ --no-sketchup-launch --no-sketchup-stop
```

## Architecture

### Test Structure

```
tests/
├── conftest.py              # Pytest fixtures
├── helpers/
│   ├── sketchup_process.py  # SketchUp process management
│   └── cli_runner.py        # CLI wrapper for supex commands
└── e2e/
    ├── test_connection.py   # Connection and basic communication
    ├── test_model_operations.py  # Geometry creation and manipulation
    └── test_introspection.py     # Model introspection tools
```

### How It Works

1. **Session Fixture** (`sketchup`) - Launches SketchUp once at test session start
2. **CLI Runner** - Wraps `supex` CLI commands for easy testing
3. **Fresh Model Fixture** - Clears model before each test
4. **No Pre-made Files** - All test geometry is created dynamically via Ruby code

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
- Helper methods: `new_model()`, `clear_model()`

## Troubleshooting

### Welcome Screen Appears on Startup

**Problem:** SketchUp shows the Welcome screen instead of opening a model directly.

**Solution:** Disable the Welcome screen in SketchUp preferences:

1. Open SketchUp
2. Go to **Window → Preferences** (or **SketchUp → Settings** on macOS)
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

## Writing New Tests

### Example Test

```python
from helpers.cli_runner import CLIRunner

def test_create_box(fresh_model: CLIRunner) -> None:
    """Create a simple box and verify it exists."""
    cli = fresh_model

    code = """
model = Sketchup.active_model
model.start_operation('Create Box', true)
face = model.entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
face.pushpull(-1.m)
model.commit_operation
model.entities.grep(Sketchup::Face).length
"""
    result = cli.eval(code.strip())
    assert result.success
    assert "6" in result.stdout  # Box has 6 faces
```

### Best Practices

1. **Use `fresh_model` fixture** - Ensures clean state for each test
2. **Wrap operations** - Always use `start_operation`/`commit_operation`
3. **Test via introspection** - Verify results with entity counts, properties
4. **Keep tests isolated** - Don't depend on state from other tests
5. **Use metric units** - `1.m` for meters, `1.cm` for centimeters

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
