# Test Ruby Snippets

This directory contains Ruby code snippets extracted from Python test files to enable proper IDE support, syntax highlighting, and SketchUp API validation.

## Directory Structure

```
tests/snippets/
├── README.md           # This file - documentation
├── .envrc              # direnv configuration (optional)
├── .mise.toml          # mise configuration (optional)
└── src/                # Ruby source files
    ├── conftest.rb
    ├── helpers.rb
    ├── test_introspection.rb
    └── test_model_operations.rb
```

**Organization**: All Ruby code (`.rb` files) is in the `src/` subdirectory to keep the root clean for configuration and documentation files.

## Motivation

Previously, Ruby code was embedded directly in Python test files using HEREDOC strings (triple-quoted strings). While functional, this approach had several drawbacks:

1. **No IDE Support**: IntelliJ and other IDEs couldn't provide syntax highlighting, autocomplete, or error detection for Ruby code embedded in Python strings
2. **No SketchUp API Validation**: IDEs couldn't validate SketchUp API calls or offer documentation for SketchUp classes/methods
3. **Difficult to Maintain**: Large blocks of Ruby code in Python files were harder to read and maintain
4. **No Linting**: RuboCop and other Ruby linters couldn't analyze embedded Ruby code

By extracting Ruby code into separate `.rb` files organized in this directory, we gain:

- Full IDE support with syntax highlighting and autocomplete
- SketchUp API documentation and validation (when configured)
- RuboCop integration for code quality
- Better organization and reusability
- Easier maintenance and refactoring

## Design Decisions

### 1. Organization: By Test File in src/ Subdirectory

Ruby snippets are organized into `.rb` files in the `src/` subdirectory that mirror their corresponding Python test files:

```
tests/snippets/src/
├── conftest.rb              # Snippets from tests/conftest.py
├── test_introspection.rb    # Snippets from tests/e2e/test_introspection.py
├── test_model_operations.rb # Snippets from tests/e2e/test_model_operations.py
└── helpers.rb               # Snippets from tests/helpers/cli_runner.py
```

**Why in src/?** Keeps the project root clean - configuration files (mise, direnv) and documentation stay at the root level, while all Ruby code is organized in the `src/` subdirectory.

**Why by test file?** Makes it easy to locate the Ruby code corresponding to a specific Python test. When working on `test_introspection.py`, you know exactly where to find the Ruby snippets.

### 2. Loading Mechanism: Full File Loading

All Ruby snippet files are loaded once at test session start:

```python
# In conftest.py - session fixture
cli_runner = CLIRunner()
cli_runner.load_snippets()  # Loads all .rb files once

# In tests - call functions directly
cli.call_snippet('geom_add_face')
```

**How it works:**
- `loader.rb` loads all `.rb` files from `src/` at session start
- All Ruby functions become available in SketchUp's Ruby context
- Tests call functions by name using `call_snippet()`
- **Ruby errors preserve file/line context** - stacktraces show actual .rb files!

**Key advantage:** When Ruby errors occur, you see the exact file and line number in the `.rb` file, making debugging much easier.

### 3. Naming Convention: Prefixed by Category

Ruby functions are named with category prefixes to avoid naming collisions and improve discoverability:

- `fixture_*` - Setup/teardown operations (e.g., `fixture_clear_all`, `fixture_clear_entities`)
- `geom_*` - Geometry creation (e.g., `geom_create_cube`, `geom_add_face`)
- `group_*` - Group operations (e.g., `group_create_named`, `group_create_nested`)
- `component_*` - Component operations (e.g., `component_create`)
- `material_*` - Material operations (e.g., `material_create_blue`)
- `layer_*` - Layer operations (e.g., `layer_create`)
- `selection_*` - Selection operations (e.g., `selection_add_face`)
- `camera_*` - Camera operations (e.g., `camera_set_position`)

### 4. Simple One-liners: Keep Inline

Very simple Ruby expressions (e.g., `"1 + 1"`, `"Sketchup.version"`) remain inline in Python tests. Only multi-line Ruby blocks are extracted.

## Usage

### In Python Tests

```python
# Call a Ruby snippet function (no parameters)
result = cli.call_snippet('geom_create_cube')

# Call with parameters
result = cli.call_snippet('some_function', 'arg1', 42, True)

# All snippets are already loaded at session start via conftest.py
# Just call them by name!
```

### Ruby Snippet Structure

Each `.rb` file in `src/` contains functions wrapped in the `SupexTestSnippets` module:

```ruby
# src/test_introspection.rb

module SupexTestSnippets
  def self.geom_add_face
    model = Sketchup.active_model
    model.start_operation('Add Geometry', true)
    model.entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
    model.commit_operation
  end

  def self.geom_add_edges
    model = Sketchup.active_model
    model.start_operation('Add Edges', true)
    model.entities.add_line([0,0,0], [1.m,0,0])
    model.entities.add_line([1.m,0,0], [1.m,1.m,0])
    model.commit_operation
  end

  # ... more functions
end
```

**Module Benefits:**
- **Namespace isolation** - functions don't pollute global scope
- **No naming conflicts** - prevents collisions with SketchUp API or other code
- **Explicit organization** - clear that these are test snippets

**How Loading Works:**

1. `loader.rb` loads all `.rb` files at session start using `require`
2. All functions become available in `SupexTestSnippets` module
3. Python calls them using `cli.call_snippet('function_name')` (module prefix added automatically)
4. **Errors show the actual file and line** - making debugging easy!

## IDE Setup

### IntelliJ IDEA / RubyMine

1. **Mark src/ as Ruby Source**:
   - Right-click `tests/snippets/src/` → Mark Directory as → Sources Root

2. **Configure Ruby SDK**:
   - File → Project Structure → SDKs
   - Add Ruby 2.7.0 (SketchUp 2020+ uses Ruby 2.7)
   - If using mise, it will automatically detect the Ruby version

3. **Install SketchUp Ruby API Stubs** (Optional):
   - For full SketchUp API documentation and autocomplete
   - Add SketchUp API gem or stubs to your Ruby SDK configuration
   - See: https://github.com/SketchUp/sketchup-ruby-api-stubs

4. **Enable RuboCop** (Optional):
   - Install RuboCop gem: `gem install rubocop`
   - Configure in Preferences → Tools → RuboCop
   - RuboCop will now analyze the Ruby snippets

### VS Code

1. **Install Ruby Extension**:
   - Install the "Ruby" extension by Shopify

2. **Configure Ruby Version**:
   - If using mise/direnv, Ruby version will be automatically detected
   - Alternatively, set `ruby.interpreter.commandPath` in settings

3. **SketchUp API Support**:
   - Install SketchUp API stubs gem for full API support
   - Configure the gem path in Ruby extension settings

### mise / direnv Setup

This project uses **mise** (formerly rtx) and **direnv** for environment management instead of `.ruby-version`.

**mise configuration** (`.mise.toml` in this directory):
- Automatically sets Ruby 2.7.0 when entering this directory
- Manages Ruby installation and PATH

**direnv configuration** (`.envrc` in this directory):
- Activates mise environment
- Can set additional environment variables

To use:
```bash
# Install mise
brew install mise

# Install direnv
brew install direnv

# Allow direnv for this directory
cd tests/snippets
direnv allow
```


## Benefits Summary

| Aspect | Before (Inline) | After (Loaded Files) |
|--------|----------------|---------------------|
| Syntax Highlighting | ❌ None | Full Ruby support |
| IDE Autocomplete | ❌ No | Yes |
| SketchUp API Docs | ❌ No | Yes (with setup) |
| RuboCop Linting | ❌ No | Yes |
| Code Navigation | ❌ Difficult | Easy |
| Refactoring | ❌ Manual | IDE-assisted |
| Reusability | ❌ Copy-paste | Shared functions |
| Organization | ❌ Mixed in Python | Clean src/ directory |
| **Error Context** | ❌ No file/line info | **Actual file:line in errors!** |
| Debugging | ❌ Hard | Easy with stacktraces |

## Future Improvements

Potential enhancements for the future:

1. **SketchUp API Stubs**: Package SketchUp API stubs for easier IDE setup
2. **Snippet Documentation**: Add Ruby comments documenting expected outputs/behavior
3. **Test Data Separation**: Extract test data (coordinates, colors, etc.) into constants
4. **Snippet Categories**: Further organize snippets into subdirectories by category
5. **Driver Refactoring**: Apply the same pattern to `driver/` Ruby code (planned separately)
