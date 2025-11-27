#!/usr/bin/env bash

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "==> Cleaning previous output..."
rm -rf generated-sketchup-api-docs/
rm -rf tmp/yard-html/

echo "==> Checking for sketchup-api-stubs submodule..."
if [ ! -d "sketchup-api-stubs/lib" ]; then
    echo "ERROR: sketchup-api-stubs submodule not found!"
    echo "Please initialize it first:"
    echo "  git submodule update --init --recursive"
    exit 1
fi

echo "==> Parsing SketchUp API with YARD..."
bundle exec yardoc

echo "==> Generating Markdown documentation from YARD registry..."
bundle exec ruby scripts/generate_sketchup_api_docs.rb

echo "==> Building INDEX.md for Claude Code..."
bundle exec ruby scripts/build_sketchup_api_index.rb

echo "==> Cleaning up temporary files..."
rm -rf tmp/

echo ""
echo "==> Documentation generated successfully!"
echo "    Output: generated-sketchup-api-docs/"
echo "    Index: generated-sketchup-api-docs/INDEX.md"
