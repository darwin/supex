# Supex Mock

Headless SketchUp API mock server for integration testing without a running SketchUp instance.

## Overview

Supex Mock provides comprehensive SketchUp Ruby API mocks that allow the Supex runtime
bridge server to run in a standalone Ruby process. Python integration tests connect
over TCP exactly like they connect to real SketchUp.

- **SketchUp API Mocks**: Geometry, entities, model, materials, layers, camera, UI
- **Test Control**: `_test.*` JSON-RPC tools for test setup/teardown
- **Blocking Event Loop**: Replaces SketchUp's UI thread for headless operation

## Project Structure

```
mock/
+-- Gemfile                # Dependencies
+-- Rakefile               # Build tasks
+-- src/
|   +-- sketchup_mock.rb         # Server launcher (entry point)
|   +-- test_control.rb    # Test control API (_test.* handlers)
|   +-- sketchup_api/      # SketchUp API mock library
|       +-- core.rb        # Loader for all mock modules
|       +-- model.rb       # Model mock
|       +-- entities.rb    # Entities collection mock
|       +-- geometry.rb    # Point3d, Vector3d, BoundingBox
|       +-- face.rb        # Face mock
|       +-- camera.rb      # Camera mock
|       +-- materials.rb   # Materials mock
|       +-- layers.rb      # Layers/Tags mock
|       +-- ui.rb          # UI mock with blocking mode
|       +-- ...
+-- test/
    +-- test_mock_api.rb   # Mock API verification tests
```

## Usage

### Starting the Mock Server

```bash
# From repository root
./scripts/launch-sketchup-mock.sh

# Or directly
ruby mock/src/sketchup_mock.rb --port 9876
```

### Test Control Tools

The mock server exposes `_test.*` JSON-RPC methods for test fixtures:

| Tool | Description |
|------|-------------|
| `_test.reset` | Reset model state to clean |
| `_test.add_definition` | Create ComponentDefinition |
| `_test.add_instance` | Place component instance |
| `_test.add_entity` | Add Face/Edge/Group |
| `_test.set_attribute` | Set attribute on entity |
| `_test.get_entity` | Get entity state (for assertions) |
| `_test.set_manifold` | Configure manifold state |
| `_test.get_state` | Full model state snapshot |

## Development

### Setup

```bash
cd mock
bundle install
```

### Commands

| Command | Description |
|---------|-------------|
| `bundle exec rake test` | Run test suite |
| `bundle exec rake rubocop` | Code linting |
| `bundle exec rubocop -A` | Auto-fix lint issues |
| `bundle exec rake yard` | Generate API docs |
