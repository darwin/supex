# IDE Stubs for SketchUp Development

This directory contains shim files that help IDEs (IntelliJ IDEA, RubyMine) resolve SketchUp's built-in modules.

## Problem

SketchUp Ruby code uses:
```ruby
require 'sketchup'
require 'extensions'
```

These modules are **built-in** to SketchUp's Ruby interpreter - they don't exist as actual `.rb` files on disk. When you run code inside SketchUp, these requires work automatically.

However, IDEs don't know about SketchUp's special environment. They look for actual files matching the require path and show "Cannot find file" warnings when they can't resolve them.

The `sketchup-api-stubs` gem provides type information for autocompletion, but its entry point is `require 'sketchup-api-stubs'`, not `require 'sketchup'`. So the IDE still can't resolve the standard SketchUp requires.

## Solution

These shim files act as bridges:
- `sketchup.rb` - allows IDE to resolve `require 'sketchup'`
- `extensions.rb` - allows IDE to resolve `require 'extensions'`

Both files simply load the `sketchup-api-stubs` gem, which provides the type definitions.

## Setup in IntelliJ IDEA / RubyMine

1. Open **File -> Project Structure** (Cmd+;)
2. Select **Modules -> runtime**
3. Go to **Load Path** tab
4. Click **+** and add this directory: `runtime/ide_stubs`
5. Click **Apply**

After this, the red underlines on `require 'sketchup'` and `require 'extensions'` should disappear, and autocompletion for SketchUp API should work.

## Note

These files are **only used by the IDE** for code analysis. They are never executed in actual SketchUp runtime, where the real built-in modules take precedence.
