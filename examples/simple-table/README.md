# Simple Table Example

This example demonstrates the project-based workflow for Supex, modeling a simple table in SketchUp using Ruby scripts.

## Project Structure

```
simple-table/
├── README.md           # This file
├── scripts/
│   ├── create_table.rb     # Main script that creates the table
│   └── add_decorations.rb  # Additional script to add decorative elements
└── model.skp           # (Created by running the scripts)
```

## Workflow

### 1. Setup

Make sure SketchUp is running with the Supex extension loaded:

```bash
cd /path/to/supex
./scripts/launch-sketchup.sh
```

### 2. Run the Scripts

In Claude Code with Supex configured, you can:

**Create the basic table:**
```
Execute scripts/create_table.rb to build the table structure
```

**Add decorative elements:**
```
Execute scripts/add_decorations.rb to add details
```

### 3. Verify Results

Use introspection tools to verify:

```
get_model_info()        # Check entity counts
take_screenshot()       # Get visual preview
list_entities('groups') # See created groups
```

### 4. Save the Model

```
save_model("model.skp")  # Save to project directory
```

## Key Features Demonstrated

1. **Project-Based Workflow**: Ruby scripts live in your project
2. **Git Tracking**: All scripts can be version controlled
3. **IDE Integration**: Edit scripts with full syntax highlighting
4. **Iterative Development**: Modify scripts and re-run
5. **Introspection**: Verify results without writing Ruby code
6. **Modular Organization**: Separate scripts for different features

## Modifying the Example

Feel free to edit the Ruby scripts:
- Change dimensions in `create_table.rb`
- Modify materials and colors
- Add new decorative elements
- Experiment with different geometries

All changes are immediately testable by re-running `eval_ruby_file`.
